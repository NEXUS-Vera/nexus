import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { Artifact } from '@nexus/contracts';
import phase12Artifact from '../../../../../packages/contracts/examples/valid/phase-12-component-plan/component-plan-artifact.json';
import greenhouseArtifact from '../../../../../packages/contracts/examples/valid/greenhouse-sensing-node/component-plan-artifact.json';
import { ComponentPlanWorkspace } from './workspace';

const phase12 = phase12Artifact as unknown as Extract<Artifact, { artifactType: 'component-plan' }>;
const greenhouse = greenhouseArtifact as unknown as Extract<
  Artifact,
  { artifactType: 'component-plan' }
>;

function stubFetch404() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: async () => '',
    }),
  );
}

describe('ComponentPlanWorkspace', () => {
  it('renders summary table, decision tab, and approve action', async () => {
    const user = userEvent.setup();
    const onSelectRole = vi.fn();
    const onSubmitTurn = vi.fn().mockResolvedValue(true);
    stubFetch404();

    render(
      <ComponentPlanWorkspace
        projectId={phase12.projectId}
        artifact={phase12}
        isDark={false}
        selectedRoleId={phase12.content.componentRoles[0].componentRoleId}
        onSelectRole={onSelectRole}
        onSubmitTurn={onSubmitTurn}
      />,
    );

    expect(screen.getByTestId('component-plan-summary')).toHaveTextContent(/candidates-proposed/i);
    expect(screen.getByTestId('component-plan-summary')).toHaveTextContent(/Preferred/i);
    expect(screen.getByTestId('component-plan-role-table')).toBeInTheDocument();
    expect(screen.getByTestId('component-plan-role-list')).toHaveTextContent(
      /Ambient temperature sensor/i,
    );
    expect(screen.getByTestId('component-plan-selection-panel')).toHaveTextContent(
      /Preferred provisional candidate/i,
    );

    await user.click(screen.getByTestId('component-plan-inspector-tab-alternatives'));
    expect(screen.getByTestId('component-plan-candidate-compare')).toBeInTheDocument();
    // Phase-12 fixture has a single preferred candidate — alternatives tab stays honest.
    expect(screen.getByTestId('component-plan-candidate-compare')).toHaveTextContent(
      /Only the preferred candidate|Fixture TMP117-class/i,
    );

    await user.click(screen.getByTestId('component-plan-inspector-tab-decision'));
    await user.click(screen.getByTestId('component-plan-approve'));
    expect(onSubmitTurn).toHaveBeenCalledWith(
      expect.stringMatching(/Approve the preferred selection for role Ambient temperature sensor/i),
    );
  });

  it('calls onRequestAlternatives without submitting a turn', async () => {
    const user = userEvent.setup();
    const onRequestAlternatives = vi.fn();
    const onSubmitTurn = vi.fn().mockResolvedValue(true);
    stubFetch404();

    const role = phase12.content.componentRoles[0];
    render(
      <ComponentPlanWorkspace
        projectId={phase12.projectId}
        artifact={phase12}
        isDark={false}
        selectedRoleId={role.componentRoleId}
        onSubmitTurn={onSubmitTurn}
        onRequestAlternatives={onRequestAlternatives}
      />,
    );

    await user.click(screen.getByTestId('component-plan-request-alternatives'));
    expect(onRequestAlternatives).toHaveBeenCalledWith(
      role.componentRoleId,
      `Show me alternatives for the ${role.name} role.`,
    );
    expect(onSubmitTurn).not.toHaveBeenCalled();
  });

  it('shows honest empty candidate and selection states for roles without candidates', () => {
    stubFetch404();

    const emptyArtifact = {
      ...greenhouse,
      content: {
        ...greenhouse.content,
        candidates: [],
        selectionDecisions: [],
        compatibilityChecks: [],
        maturity: 'roles-defined' as const,
      },
    };

    render(
      <ComponentPlanWorkspace
        projectId={emptyArtifact.projectId}
        artifact={emptyArtifact}
        isDark={false}
        selectedRoleId={emptyArtifact.content.componentRoles[0].componentRoleId}
      />,
    );

    expect(screen.getByTestId('component-plan-role-list')).toHaveTextContent(
      /No candidate proposed/i,
    );
    expect(screen.getByTestId('component-plan-selection-empty')).toHaveTextContent(
      /No preferred selection yet/i,
    );
  });

  it('renders empty state when artifact is missing', () => {
    render(<ComponentPlanWorkspace projectId="proj_missing" isDark={false} />);
    expect(screen.getByTestId('component-plan-empty')).toHaveTextContent(
      /Component plan not available/i,
    );
  });

  it('selects a sensor role from the component table', async () => {
    const user = userEvent.setup();
    const onSelectRole = vi.fn();
    stubFetch404();

    const sensorRole = greenhouse.content.componentRoles[0];
    render(
      <ComponentPlanWorkspace
        projectId={greenhouse.projectId}
        artifact={greenhouse}
        isDark={false}
        selectedRoleId={sensorRole.componentRoleId}
        onSelectRole={onSelectRole}
      />,
    );

    const roleRow = screen.getByTestId(`component-role-${sensorRole.componentRoleId}`);
    expect(roleRow).toHaveAttribute('data-role-category', 'sensor');
    await user.click(roleRow);
    expect(onSelectRole).toHaveBeenCalledWith(sensorRole.componentRoleId);
  });

  it('switches inspector tabs for specs evidence and linked work', async () => {
    const user = userEvent.setup();
    stubFetch404();

    render(
      <ComponentPlanWorkspace
        projectId={phase12.projectId}
        artifact={phase12}
        isDark={false}
        selectedRoleId={phase12.content.componentRoles[0].componentRoleId}
      />,
    );

    await user.click(screen.getByTestId('component-plan-inspector-tab-specifications'));
    expect(screen.getByTestId('component-plan-specs')).toBeInTheDocument();

    await user.click(screen.getByTestId('component-plan-inspector-tab-evidence'));
    expect(screen.getByTestId('component-plan-evidence')).toBeInTheDocument();

    await user.click(screen.getByTestId('component-plan-inspector-tab-linked-work'));
    expect(screen.getByTestId('component-plan-linked-work')).toBeInTheDocument();
  });
});
