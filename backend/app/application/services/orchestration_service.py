import hashlib
import json
import re
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.domain.enums import ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import (
    AgentCapability,
    AgentCapabilityVersion,
    AgentTool,
    AnalysisRun,
    AnalysisRunOrchestrationSnapshot,
    InputSnapshot,
    OrchestrationTemplate,
    OrchestrationTemplateNode,
    TaskOrchestrationBinding,
    VerificationCycle,
    VerificationTask,
)


_KEY = re.compile(r"^[a-z][a-z0-9-]{2,95}$")
_CORE_KEYS = {"requirement-claim-core", "delivery-git-diff", "evidence-reconciliation"}
_SYSTEM_CAPABILITIES = (
    ("requirement-claim-core", "需求/验收核验核心", "REQUIREMENT", True, "从冻结的需求和验收资料提取可引用 Claim。", ["document-retrieval"]),
    ("delivery-git-diff", "Git Diff 代码证据", "DELIVERY", True, "读取冻结 Git 范围并生成可定位的代码证据。", ["git-diff-reader"]),
    ("ci-evidence-import", "CI 测试与构建证据", "DELIVERY", False, "导入与冻结目标提交绑定的测试和构建证据。", ["ci-evidence-reader"]),
    ("risk-scan", "交付风险扫描", "SHARED", False, "根据已授权证据标记需要人工确认的交付风险。", ["evidence-query"]),
    ("model-link-proposal", "证据关联建议", "SHARED", False, "由模型提出候选关联，不能直接决定正式结论。", ["evidence-query"]),
    ("evidence-reconciliation", "证据裁决与 Coverage", "SHARED", True, "校验引用、应用权威规则并生成正式核验结果。", ["evidence-query"]),
    ("report-draft", "报告草稿", "SHARED", False, "把已持久化结果整理为可编辑报告草稿。", ["evidence-query"]),
)
_SYSTEM_TOOLS = (
    ("document-retrieval", "资料检索", "DOCUMENT_RETRIEVAL"),
    ("git-diff-reader", "Git Diff 只读", "GIT_DIFF"),
    ("ci-evidence-reader", "CI 证据读取", "CI_EVIDENCE"),
    ("evidence-query", "证据查询", "EVIDENCE_QUERY"),
)


def _hash(value: object) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"


def _validate_key(key: str) -> str:
    normalized = key.strip().lower()
    if not _KEY.fullmatch(normalized):
        raise DomainError("INPUT_INVALID", "标识仅允许小写字母、数字和连字符，且长度为 3-96")
    return normalized


def _assert_tools(session: Session, *, project_id: UUID, tool_ids: list[UUID]) -> list[AgentTool]:
    if len(tool_ids) != len(set(tool_ids)):
        raise DomainError("INPUT_INVALID", "工具不能重复授权")
    tools = session.query(AgentTool).filter(AgentTool.id.in_(tool_ids), AgentTool.project_id == project_id, AgentTool.is_active.is_(True)).all() if tool_ids else []
    if len(tools) != len(tool_ids):
        raise DomainError("INPUT_INVALID", "工具不存在、无权限或已停用")
    return tools


def ensure_default_orchestration(session: Session, *, project_id: UUID, actor_id: UUID) -> OrchestrationTemplate:
    existing = session.query(OrchestrationTemplate).filter_by(project_id=project_id, is_default=True).one_or_none()
    if existing is not None:
        return existing

    tools: dict[str, AgentTool] = {}
    for key, name, tool_type in _SYSTEM_TOOLS:
        tool = AgentTool(project_id=project_id, key=key, name=name, tool_type=tool_type, is_system=True, created_by=actor_id)
        session.add(tool)
        tools[key] = tool
    session.flush()

    versions: dict[str, AgentCapabilityVersion] = {}
    for key, name, scope, locked, description, tool_keys in _SYSTEM_CAPABILITIES:
        capability = AgentCapability(
            project_id=project_id,
            key=key,
            name=name,
            description=description,
            core_scope=scope,
            kind="SYSTEM",
            is_locked=locked,
            is_default_enabled=True,
            created_by=actor_id,
        )
        session.add(capability)
        session.flush()
        bindings = [{"toolId": str(tools[tool_key].id), "key": tool_key} for tool_key in tool_keys]
        content = {"key": key, "prompt": "", "input": {}, "output": {}, "tools": bindings, "parameters": {}}
        version = AgentCapabilityVersion(
            capability_id=capability.id,
            version_no=1,
            tool_bindings=bindings,
            content_hash=_hash(content),
            created_by=actor_id,
        )
        session.add(version)
        versions[key] = version
    session.flush()

    template = OrchestrationTemplate(
        project_id=project_id,
        name="默认交付核验",
        description="固定双核、锁定 Git Diff，并按证据协议执行的默认模板。",
        is_default=True,
        is_system=True,
        created_by=actor_id,
    )
    session.add(template)
    session.flush()
    for order, (key, _, scope, locked, _, _) in enumerate(_SYSTEM_CAPABILITIES, start=1):
        session.add(OrchestrationTemplateNode(
            template_id=template.id,
            capability_version_id=versions[key].id,
            core_scope=scope,
            display_order=order,
            enabled=True,
            parameters={"locked": locked},
        ))
    session.flush()
    return template


def bind_task_default_orchestration(session: Session, *, task_id: UUID, project_id: UUID, actor_id: UUID) -> TaskOrchestrationBinding:
    existing = session.query(TaskOrchestrationBinding).filter_by(task_id=task_id).one_or_none()
    if existing is not None:
        return existing
    template = ensure_default_orchestration(session, project_id=project_id, actor_id=actor_id)
    binding = TaskOrchestrationBinding(task_id=task_id, template_id=template.id, template_version=template.version, bound_by=actor_id)
    session.add(binding)
    session.flush()
    return binding


def _template_nodes(session: Session, template_id: UUID) -> list[tuple[OrchestrationTemplateNode, AgentCapabilityVersion, AgentCapability]]:
    return (
        session.query(OrchestrationTemplateNode, AgentCapabilityVersion, AgentCapability)
        .join(AgentCapabilityVersion, AgentCapabilityVersion.id == OrchestrationTemplateNode.capability_version_id)
        .join(AgentCapability, AgentCapability.id == AgentCapabilityVersion.capability_id)
        .filter(OrchestrationTemplateNode.template_id == template_id)
        .order_by(OrchestrationTemplateNode.display_order)
        .all()
    )


def _validate_template_nodes(session: Session, *, project_id: UUID, nodes: list[dict]) -> list[tuple[AgentCapabilityVersion, AgentCapability, dict]]:
    if not nodes:
        raise DomainError("INPUT_INVALID", "编排模板至少需要一个能力块")
    version_ids = [UUID(str(node["capability_version_id"])) for node in nodes]
    if len(version_ids) != len(set(version_ids)):
        raise DomainError("INPUT_INVALID", "同一能力版本不能在模板中重复出现")
    rows = (
        session.query(AgentCapabilityVersion, AgentCapability)
        .join(AgentCapability, AgentCapability.id == AgentCapabilityVersion.capability_id)
        .filter(AgentCapabilityVersion.id.in_(version_ids), AgentCapability.project_id == project_id, AgentCapability.is_active.is_(True))
        .all()
    )
    if len(rows) != len(version_ids):
        raise DomainError("INPUT_INVALID", "能力块版本不存在、无权限或已停用")
    by_id = {str(version.id): (version, capability) for version, capability in rows}
    resolved: list[tuple[AgentCapabilityVersion, AgentCapability, dict]] = []
    for node in nodes:
        version, capability = by_id[str(node["capability_version_id"])]
        enabled = bool(node.get("enabled", True))
        if capability.is_locked and not enabled:
            raise DomainError("INPUT_INVALID", f"系统主干能力 {capability.name} 不可停用")
        resolved.append((version, capability, {"enabled": enabled, "parameters": node.get("parameters", {})}))
    mandatory = {"requirement-claim-core", "delivery-git-diff", "evidence-reconciliation"}
    enabled_keys = {capability.key for _, capability, node in resolved if node["enabled"]}
    if not mandatory.issubset(enabled_keys):
        raise DomainError("INPUT_INVALID", "模板必须包含需求核心、锁定 Git Diff 和证据裁决主干")
    return resolved


def create_custom_capability(
    session: Session,
    *,
    project_id: UUID,
    actor_id: UUID,
    correlation_id: str,
    key: str,
    name: str,
    description: str,
    core_scope: str,
    prompt_template: str,
    input_schema: dict,
    output_schema: dict,
    parameter_schema: dict,
    tool_ids: list[UUID],
) -> AgentCapability:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if core_scope not in {"REQUIREMENT", "DELIVERY", "SHARED"}:
        raise DomainError("INPUT_INVALID", "能力块归属必须为 REQUIREMENT、DELIVERY 或 SHARED")
    key = _validate_key(key)
    if session.query(AgentCapability).filter_by(project_id=project_id, key=key).one_or_none() is not None:
        raise DomainError("STATE_CONFLICT", "项目内能力块标识已存在")
    tools = _assert_tools(session, project_id=project_id, tool_ids=tool_ids)
    capability = AgentCapability(project_id=project_id, key=key, name=name.strip(), description=description.strip(), core_scope=core_scope, kind="CUSTOM", created_by=actor_id)
    session.add(capability)
    session.flush()
    bindings = [{"toolId": str(tool.id), "key": tool.key, "type": tool.tool_type} for tool in tools]
    content = {"key": key, "prompt": prompt_template, "input": input_schema, "output": output_schema, "tools": bindings, "parameters": parameter_schema}
    session.add(AgentCapabilityVersion(capability_id=capability.id, version_no=1, prompt_template=prompt_template, input_schema=input_schema, output_schema=output_schema, tool_bindings=bindings, parameter_schema=parameter_schema, content_hash=_hash(content), created_by=actor_id))
    append_audit_event(session, project_id=project_id, actor_id=actor_id, aggregate_type="AgentCapability", aggregate_id=capability.id, action="AGENT_CAPABILITY_CREATED", correlation_id=correlation_id)
    return capability


def create_capability_version(
    session: Session,
    *,
    capability_id: UUID,
    actor_id: UUID,
    correlation_id: str,
    prompt_template: str,
    input_schema: dict,
    output_schema: dict,
    parameter_schema: dict,
    tool_ids: list[UUID],
) -> AgentCapabilityVersion:
    capability = session.get(AgentCapability, capability_id)
    if capability is None:
        raise DomainError("RESOURCE_NOT_FOUND", "能力块不存在")
    require_project_role(session, capability.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if capability.kind == "SYSTEM":
        raise DomainError("AUTH_FORBIDDEN", "系统主干能力不能编辑 Prompt 或工具授权")
    tools = _assert_tools(session, project_id=capability.project_id, tool_ids=tool_ids)
    previous = session.query(func.coalesce(func.max(AgentCapabilityVersion.version_no), 0)).filter_by(capability_id=capability.id).scalar()
    bindings = [{"toolId": str(tool.id), "key": tool.key, "type": tool.tool_type} for tool in tools]
    content = {"key": capability.key, "prompt": prompt_template, "input": input_schema, "output": output_schema, "tools": bindings, "parameters": parameter_schema}
    version = AgentCapabilityVersion(capability_id=capability.id, version_no=previous + 1, prompt_template=prompt_template, input_schema=input_schema, output_schema=output_schema, tool_bindings=bindings, parameter_schema=parameter_schema, content_hash=_hash(content), created_by=actor_id)
    session.add(version)
    session.flush()
    append_audit_event(session, project_id=capability.project_id, actor_id=actor_id, aggregate_type="AgentCapability", aggregate_id=capability.id, action="AGENT_CAPABILITY_VERSION_CREATED", correlation_id=correlation_id, payload={"version": version.version_no})
    return version


def create_custom_tool(session: Session, *, project_id: UUID, actor_id: UUID, correlation_id: str, key: str, name: str, tool_type: str, endpoint_url: str | None, secret_ref: str | None, input_schema: dict, output_schema: dict) -> AgentTool:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if tool_type not in {"DOCUMENT_RETRIEVAL", "GIT_DIFF", "CI_EVIDENCE", "EVIDENCE_QUERY", "HTTP_QUERY"}:
        raise DomainError("INPUT_INVALID", "不支持的工具类型")
    if tool_type == "HTTP_QUERY" and not endpoint_url:
        raise DomainError("INPUT_INVALID", "HTTP 查询工具必须提供登记的只读端点")
    if tool_type != "HTTP_QUERY" and endpoint_url:
        raise DomainError("INPUT_INVALID", "内置只读工具不能配置外部端点")
    key = _validate_key(key)
    if session.query(AgentTool).filter_by(project_id=project_id, key=key).one_or_none() is not None:
        raise DomainError("STATE_CONFLICT", "项目内工具标识已存在")
    tool = AgentTool(project_id=project_id, key=key, name=name.strip(), tool_type=tool_type, endpoint_url=endpoint_url, secret_ref=secret_ref, input_schema=input_schema, output_schema=output_schema, created_by=actor_id)
    session.add(tool)
    session.flush()
    append_audit_event(session, project_id=project_id, actor_id=actor_id, aggregate_type="AgentTool", aggregate_id=tool.id, action="AGENT_TOOL_CREATED", correlation_id=correlation_id)
    return tool


def create_template(session: Session, *, project_id: UUID, actor_id: UUID, correlation_id: str, name: str, description: str, nodes: list[dict]) -> OrchestrationTemplate:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if session.query(OrchestrationTemplate).filter_by(project_id=project_id, name=name.strip()).one_or_none() is not None:
        raise DomainError("STATE_CONFLICT", "项目内编排模板名称已存在")
    resolved = _validate_template_nodes(session, project_id=project_id, nodes=nodes)
    template = OrchestrationTemplate(project_id=project_id, name=name.strip(), description=description.strip(), created_by=actor_id)
    session.add(template)
    session.flush()
    for order, (version, capability, node) in enumerate(resolved, start=1):
        session.add(OrchestrationTemplateNode(template_id=template.id, capability_version_id=version.id, core_scope=capability.core_scope, display_order=order, enabled=node["enabled"], parameters=node["parameters"]))
    append_audit_event(session, project_id=project_id, actor_id=actor_id, aggregate_type="OrchestrationTemplate", aggregate_id=template.id, action="ORCHESTRATION_TEMPLATE_CREATED", correlation_id=correlation_id)
    return template


def bind_task_template(session: Session, *, task_id: UUID, template_id: UUID, actor_id: UUID, correlation_id: str) -> TaskOrchestrationBinding:
    task = session.get(VerificationTask, task_id)
    template = session.get(OrchestrationTemplate, template_id)
    if task is None or template is None or task.project_id != template.project_id:
        raise DomainError("RESOURCE_NOT_FOUND", "核验任务或编排模板不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    _validate_template_nodes(session, project_id=task.project_id, nodes=[{"capability_version_id": node.capability_version_id, "enabled": node.enabled, "parameters": node.parameters} for node, _, _ in _template_nodes(session, template.id)])
    binding = session.query(TaskOrchestrationBinding).filter_by(task_id=task.id).one_or_none()
    if binding is None:
        binding = TaskOrchestrationBinding(task_id=task.id, template_id=template.id, template_version=template.version, bound_by=actor_id)
        session.add(binding)
    else:
        binding.template_id = template.id
        binding.template_version = template.version
        binding.bound_by = actor_id
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="VerificationTask", aggregate_id=task.id, action="TASK_ORCHESTRATION_BOUND", correlation_id=correlation_id, payload={"templateId": str(template.id), "templateVersion": template.version})
    return binding


def _orchestration_payload(session: Session, *, task: VerificationTask, actor_id: UUID) -> tuple[OrchestrationTemplate, list[dict]]:
    binding = bind_task_default_orchestration(session, task_id=task.id, project_id=task.project_id, actor_id=actor_id)
    template = session.get(OrchestrationTemplate, binding.template_id)
    rows = _template_nodes(session, template.id)
    nodes = [
        {
            "capabilityId": str(capability.id),
            "capabilityKey": capability.key,
            "capabilityName": capability.name,
            "capabilityVersionId": str(version.id),
            "capabilityVersion": version.version_no,
            "coreScope": node.core_scope,
            "displayOrder": node.display_order,
            "enabled": node.enabled,
            "locked": capability.is_locked,
            "promptTemplate": version.prompt_template,
            "tools": version.tool_bindings,
            "parameters": node.parameters,
        }
        for node, version, capability in rows
    ]
    _validate_template_nodes(session, project_id=task.project_id, nodes=[{"capability_version_id": row[1].id, "enabled": row[0].enabled, "parameters": row[0].parameters} for row in rows])
    return template, nodes


def orchestration_fingerprint(session: Session, *, task: VerificationTask, actor_id: UUID) -> str:
    template, nodes = _orchestration_payload(session, task=task, actor_id=actor_id)
    return _hash({"template": {"id": str(template.id), "version": template.version}, "nodes": nodes})


def freeze_run_orchestration(session: Session, *, run: AnalysisRun, task: VerificationTask, actor_id: UUID) -> AnalysisRunOrchestrationSnapshot:
    template, nodes = _orchestration_payload(session, task=task, actor_id=actor_id)
    template_snapshot = {"id": str(template.id), "name": template.name, "version": template.version}
    return AnalysisRunOrchestrationSnapshot(run_id=run.id, template_id=template.id, template_version=template.version, content_hash=_hash({"template": template_snapshot, "nodes": nodes}), template_snapshot=template_snapshot, nodes_snapshot=nodes)


def list_orchestration(session: Session, *, project_id: UUID, actor_id: UUID) -> dict:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    capabilities = session.query(AgentCapability).filter_by(project_id=project_id).order_by(AgentCapability.created_at).all()
    tools = session.query(AgentTool).filter_by(project_id=project_id).order_by(AgentTool.created_at).all()
    templates = session.query(OrchestrationTemplate).filter_by(project_id=project_id).order_by(OrchestrationTemplate.is_default.desc(), OrchestrationTemplate.created_at).all()
    return {
        "capabilities": [{"id": str(item.id), "key": item.key, "name": item.name, "description": item.description, "coreScope": item.core_scope, "kind": item.kind, "isLocked": item.is_locked, "isDefaultEnabled": item.is_default_enabled, "isActive": item.is_active} for item in capabilities],
        "tools": [{"id": str(item.id), "key": item.key, "name": item.name, "toolType": item.tool_type, "endpointUrl": item.endpoint_url, "secretRef": item.secret_ref, "isSystem": item.is_system, "isActive": item.is_active} for item in tools],
        "templates": [{"id": str(item.id), "name": item.name, "description": item.description, "isDefault": item.is_default, "isSystem": item.is_system, "version": item.version, "nodes": [{"capabilityVersionId": str(version.id), "capabilityKey": capability.key, "capabilityName": capability.name, "coreScope": node.core_scope, "displayOrder": node.display_order, "enabled": node.enabled, "locked": capability.is_locked, "parameters": node.parameters} for node, version, capability in _template_nodes(session, item.id)]} for item in templates],
    }


def get_run_orchestration(session: Session, *, run_id: UUID, actor_id: UUID) -> dict:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise DomainError("RESOURCE_NOT_FOUND", "分析运行不存在")
    task = (
        session.query(VerificationTask)
        .join(VerificationCycle, VerificationCycle.task_id == VerificationTask.id)
        .join(InputSnapshot, InputSnapshot.cycle_id == VerificationCycle.id)
        .filter(InputSnapshot.id == run.snapshot_id)
        .one_or_none()
    )
    if task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "分析运行所属任务不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    snapshot = session.query(AnalysisRunOrchestrationSnapshot).filter_by(run_id=run.id).one_or_none()
    if snapshot is None:
        raise DomainError("RESOURCE_NOT_FOUND", "分析运行没有编排快照")
    return {"contentHash": snapshot.content_hash, "template": snapshot.template_snapshot, "nodes": snapshot.nodes_snapshot}
