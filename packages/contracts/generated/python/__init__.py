# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
"""Generated Nexus contract TypedDict modules."""

from .actor_reference_v1 import *  # noqa: F403
from .analysis_investigation_v1 import *  # noqa: F403
from .analysis_patch_proposal_v1 import *  # noqa: F403
from .analysis_verification_assessment_v1 import *  # noqa: F403
from .approval_record_v1 import *  # noqa: F403
from .approval_requirement_v1 import *  # noqa: F403
from .artifact_authority_v1 import *  # noqa: F403
from .artifact_command_result_v1 import *  # noqa: F403
from .artifact_command_v1 import *  # noqa: F403
from .artifact_dependency_v1 import *  # noqa: F403
from .artifact_entity_reference_v1 import *  # noqa: F403
from .artifact_envelope_v1 import *  # noqa: F403
from .artifact_proposal_v1 import *  # noqa: F403
from .artifact_status_v1 import *  # noqa: F403
from .artifact_type_definition_v1 import *  # noqa: F403
from .artifact_type_v1 import *  # noqa: F403
from .artifact_v1 import *  # noqa: F403
from .circuit_simulation_support_assessment_v1 import *  # noqa: F403
from .compatibility_check_v1 import *  # noqa: F403
from .component_candidate_v1 import *  # noqa: F403
from .component_category_v1 import *  # noqa: F403
from .component_plan_coverage_summary_v1 import *  # noqa: F403
from .component_plan_v1 import *  # noqa: F403
from .component_role_v1 import *  # noqa: F403
from .consequence_level_v1 import *  # noqa: F403
from .derived_fact_provenance_v1 import *  # noqa: F403
from .electrical_architecture_v1 import *  # noqa: F403
from .evidence_reference_v1 import *  # noqa: F403
from .execution_command_spec_v1 import *  # noqa: F403
from .execution_job_v1 import *  # noqa: F403
from .execution_log_chunk_v1 import *  # noqa: F403
from .execution_request_v1 import *  # noqa: F403
from .execution_result_v1 import *  # noqa: F403
from .execution_run_v1 import *  # noqa: F403
from .external_workspace_reference_v1 import *  # noqa: F403
from .firmware_patch_proposal_v1 import *  # noqa: F403
from .functional_architecture_v1 import *  # noqa: F403
from .graph_traversal_result_v1 import *  # noqa: F403
from .next_action_v1 import *  # noqa: F403
from .open_question_reference_v1 import *  # noqa: F403
from .open_question_v1 import *  # noqa: F403
from .physical_architecture_v1 import *  # noqa: F403
from .produced_output_v1 import *  # noqa: F403
from .project_board_projection_v1 import *  # noqa: F403
from .project_brief_v1 import *  # noqa: F403
from .project_change_intent_v1 import *  # noqa: F403
from .project_current_state_v1 import *  # noqa: F403
from .project_event_v1 import *  # noqa: F403
from .project_graph_edge_v1 import *  # noqa: F403
from .project_graph_node_v1 import *  # noqa: F403
from .project_history_v1 import *  # noqa: F403
from .project_impact_analysis_v1 import *  # noqa: F403
from .project_initialization_result_v1 import *  # noqa: F403
from .project_turn_result_v1 import *  # noqa: F403
from .project_v1 import *  # noqa: F403
from .quantity_v1 import *  # noqa: F403
from .requirement_set_v1 import *  # noqa: F403
from .risk_register_v1 import *  # noqa: F403
from .runtime_capability_v1 import *  # noqa: F403
from .selection_constraint_v1 import *  # noqa: F403
from .selection_decision_v1 import *  # noqa: F403
from .test_plan_v1 import *  # noqa: F403
from .turn_route_v1 import *  # noqa: F403
from .user_turn_v1 import *  # noqa: F403
from .validation_issue_v1 import *  # noqa: F403
from .vera_response_v1 import *  # noqa: F403
from .workflow_run_v1 import *  # noqa: F403
from .workspace_descriptor_v1 import *  # noqa: F403
from .workspace_draft_state_v1 import *  # noqa: F403
from .workspace_file_v1 import *  # noqa: F403
from .workspace_snapshot_v1 import *  # noqa: F403

__all__ = [
    "actor_reference_v1",
    "analysis_investigation_v1",
    "analysis_patch_proposal_v1",
    "analysis_verification_assessment_v1",
    "approval_record_v1",
    "approval_requirement_v1",
    "artifact_authority_v1",
    "artifact_command_result_v1",
    "artifact_command_v1",
    "artifact_dependency_v1",
    "artifact_entity_reference_v1",
    "artifact_envelope_v1",
    "artifact_proposal_v1",
    "artifact_status_v1",
    "artifact_type_definition_v1",
    "artifact_type_v1",
    "artifact_v1",
    "circuit_simulation_support_assessment_v1",
    "compatibility_check_v1",
    "component_candidate_v1",
    "component_category_v1",
    "component_plan_coverage_summary_v1",
    "component_plan_v1",
    "component_role_v1",
    "consequence_level_v1",
    "derived_fact_provenance_v1",
    "electrical_architecture_v1",
    "evidence_reference_v1",
    "execution_command_spec_v1",
    "execution_job_v1",
    "execution_log_chunk_v1",
    "execution_request_v1",
    "execution_result_v1",
    "execution_run_v1",
    "external_workspace_reference_v1",
    "firmware_patch_proposal_v1",
    "functional_architecture_v1",
    "graph_traversal_result_v1",
    "next_action_v1",
    "open_question_reference_v1",
    "open_question_v1",
    "physical_architecture_v1",
    "produced_output_v1",
    "project_board_projection_v1",
    "project_brief_v1",
    "project_change_intent_v1",
    "project_current_state_v1",
    "project_event_v1",
    "project_graph_edge_v1",
    "project_graph_node_v1",
    "project_history_v1",
    "project_impact_analysis_v1",
    "project_initialization_result_v1",
    "project_turn_result_v1",
    "project_v1",
    "quantity_v1",
    "requirement_set_v1",
    "risk_register_v1",
    "runtime_capability_v1",
    "selection_constraint_v1",
    "selection_decision_v1",
    "test_plan_v1",
    "turn_route_v1",
    "user_turn_v1",
    "validation_issue_v1",
    "vera_response_v1",
    "workflow_run_v1",
    "workspace_descriptor_v1",
    "workspace_draft_state_v1",
    "workspace_file_v1",
    "workspace_snapshot_v1",
]
