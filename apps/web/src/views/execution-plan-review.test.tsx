import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ExecutionPlanArtifact } from '../api/client';
import { ExecutionPlanReview } from './ExecutionPlanReview';

const content: ExecutionPlanArtifact['content'] = {
  configuration: {
    analysisProfileId: 'python-analysis-v1', buildProfileId: 'platformio-arduino-esp32-v1',
    components: [{ candidateId: 'esp32', componentRoleId: 'mcu' }, { candidateId: 'mpu6050', componentRoleId: 'imu' }],
    i2c: { connectionId: 'i2c', sdaPin: 21, sclPin: 22 },
  },
  plan: {
    schemaVersion: '1.0.0', status: 'proposed', basisProjectStateVersion: 1,
    sourceArtifacts: [{ artifactId: 'requirements', artifactVersion: 1 }],
    requirements: [{ artifactId: 'requirements', entityId: 'R7' }], assumptions: [], components: [], interfaces: [], openDecisionIds: [],
    workspaces: [{ artifactType: 'firmware', availability: 'planned', workspaceKey: 'firmware' }],
    verificationObjectives: [{ objectiveId: 'noise', requirementId: 'R7', method: 'analysis', acceptanceCriteria: ['RMS < 0.1 g'], workspaceKey: 'firmware' }],
    steps: [
      { stepId: 'compile', title: 'Compile firmware', dependsOn: [], objectiveIds: [], requiresApproval: true, workspaceKeys: ['firmware'] },
      { stepId: 'analyze', title: 'Analyze noise', dependsOn: ['compile'], objectiveIds: ['noise'], requiresApproval: true, workspaceKeys: ['firmware'] },
    ],
  },
};

describe('ExecutionPlanReview', () => {
  it('renders API-shaped plan dependencies, requirement objectives and pinout', () => {
    render(<ExecutionPlanReview content={content} isDark={false} onAccept={vi.fn()} onReject={vi.fn()} />);
    const steps = screen.getAllByRole('listitem');
    expect(steps[0]).toHaveTextContent('Compile firmware');
    expect(steps[0]).toHaveTextContent('Depends on: None');
    expect(steps[1]).toHaveTextContent('Depends on: compile');
    expect(steps[1]).toHaveTextContent('Requires approval');
    const table = screen.getByRole('table');
    expect(table).toHaveTextContent('R7');
    expect(table).toHaveTextContent('requirements');
    expect(table).toHaveTextContent('noise · analysis · firmware: RMS < 0.1 g');
    const pinout = screen.getByRole('region', { name: 'Pinout' });
    expect(pinout).toHaveTextContent('mcu: esp32, imu: mpu6050');
    expect(pinout).toHaveTextContent('SDA: GPIO 21 · SCL: GPIO 22');
  });

  it('delegates decisions without supplying an event or choosing a rejection reason UX', () => {
    const onAccept = vi.fn();
    const onReject = vi.fn<(reason?: string) => void>();
    render(<ExecutionPlanReview content={content} isDark onAccept={onAccept} onReject={onReject} />);
    fireEvent.click(screen.getByRole('button', { name: 'Accept plan' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reject plan' }));
    expect(onAccept).toHaveBeenCalledExactlyOnceWith();
    expect(onReject).toHaveBeenCalledExactlyOnceWith();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it.each([{}, { plan: { steps: [], requirements: [], verificationObjectives: [] } }])('handles missing or empty sections defensively', (partial) => {
    // Deliberately incomplete transport data; the public prop still uses the API type.
    render(<ExecutionPlanReview content={partial as unknown as ExecutionPlanArtifact['content']} isDark={false} onAccept={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('No steps available.')).toBeInTheDocument();
    expect(screen.getByText('No requirements available.')).toBeInTheDocument();
    expect(screen.getByText('No pinout available.')).toBeInTheDocument();
  });

  it('handles missing objectives and pinout independently', () => {
    const partial = { ...content, plan: { ...content.plan, verificationObjectives: [] }, configuration: { ...content.configuration, i2c: undefined } };
    render(<ExecutionPlanReview content={partial as unknown as ExecutionPlanArtifact['content']} isDark={false} onAccept={vi.fn()} onReject={vi.fn()} />);
    expect(within(screen.getByRole('table')).getByText('No verification objectives.')).toBeInTheDocument();
    expect(screen.getByText('No I²C pinout available.')).toBeInTheDocument();
  });
});
