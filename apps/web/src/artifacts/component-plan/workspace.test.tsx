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

describe('ComponentPlanWorkspace', () => {
  it('renders roles, candidates, and selection panel from phase-12 content', async () => {
    const user = userEvent.setup();
    const onSelectRole = vi.fn();
    const onSubmitTurn = vi.fn().mockResolvedValue(true);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: async () => '',
      }),
    );

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
    expect(screen.getByTestId('component-plan-role-list')).toHaveTextContent(
      /Ambient temperature sensor/i,
    );
    expect(screen.getByTestId('component-plan-candidate-compare')).toHaveTextContent(
      /Fixture TMP117-class/i,
    );
    expect(screen.getByTestId('component-plan-selection-panel')).toHaveTextContent(
      /Preferred provisional candidate/i,
    );

    await user.click(screen.getByTestId('component-plan-approve'));
    expect(onSubmitTurn).toHaveBeenCalledWith(
      expect.stringMatching(/Approve the preferred selection for role Ambient temperature sensor/i),
    );
  });

  it('shows honest empty candidate and selection states', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: async () => '',
      }),
    );

    render(
      <ComponentPlanWorkspace
        projectId={greenhouse.projectId}
        artifact={greenhouse}
        isDark={false}
        selectedRoleId={greenhouse.content.componentRoles[0].componentRoleId}
      />,
    );

    expect(screen.getByTestId('component-plan-role-list')).toHaveTextContent(
      /Environmental Measurement Acquisition/i,
    );
    expect(screen.getByTestId('component-plan-candidates-empty')).toHaveTextContent(
      /No candidates proposed/i,
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

  it('selects a sensor role from the role list', async () => {
    const user = userEvent.setup();
    const onSelectRole = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: async () => '',
      }),
    );

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

    const roleButton = screen.getByTestId(`component-role-${sensorRole.componentRoleId}`);
    expect(roleButton).toHaveAttribute('data-role-category', 'sensor');
    await user.click(roleButton);
    expect(onSelectRole).toHaveBeenCalledWith(sensorRole.componentRoleId);
  });
});
