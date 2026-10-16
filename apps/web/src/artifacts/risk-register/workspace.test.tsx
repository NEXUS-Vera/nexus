import { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RiskRegisterWorkspace } from './workspace';
import type { Artifact } from '@nexus/contracts';
import golden from '../../../../../packages/contracts/examples/valid/esp32-imu-vibration-monitor/risk-register-artifact.json';

function Harness() {
  const artifact = golden as unknown as Extract<Artifact, { artifactType: 'risk-register' }>;
  const [selectedRiskId, setSelectedRiskId] = useState('K6');
  return (
    <RiskRegisterWorkspace
      artifact={artifact}
      isDark={false}
      selectedRiskId={selectedRiskId}
      onSelectRisk={setSelectedRiskId}
    />
  );
}

describe('RiskRegisterWorkspace', () => {
  it('prioritizes risks and keeps K6 unresolved', () => {
    render(<Harness />);
    expect(screen.getByTestId('risk-summary-open')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('risk-item-K6'));
    expect(screen.getByTestId('risk-detail')).toHaveTextContent('monitoring');
    expect(screen.getByTestId('risk-residual')).toBeInTheDocument();
    expect(screen.getByTestId('risk-mitigation-verification')).toHaveTextContent(/monitoring/i);
    fireEvent.click(screen.getByTestId('risk-item-K5'));
    expect(screen.getByTestId('risk-verification-tests')).toHaveTextContent('T7');
    expect(screen.getByTestId('risk-mitigation-verification')).toHaveTextContent(
      /lifecycle not auto-closed/i,
    );
  });
});
