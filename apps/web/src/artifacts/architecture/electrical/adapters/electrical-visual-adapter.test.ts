import { describe, expect, it } from 'vitest';
import electricalFixture from '../../../../../../../packages/contracts/examples/valid/phase-13-electrical-architecture/electrical-architecture-artifact.json';
import { resolveElectricalNodeRenderer, flowTypeForCategory } from '../registry/node-renderers';
import { adaptElectricalVisualGraph } from './electrical-visual-adapter';
import { adaptSimulationVisualGraph } from './simulation-visual-adapter';

describe('electrical visual adapter', () => {
  it('classifies compute and sensor nodes from role/candidate categories', () => {
    const graph = adaptElectricalVisualGraph(electricalFixture.content, {
      candidatesById: {
        cand_mcu: {
          candidateId: 'cand_mcu',
          partNumber: 'FX-MCU-32',
          displayName: 'Fixture MCU',
          category: 'compute',
        },
        cand_imu: {
          candidateId: 'cand_imu',
          partNumber: 'FX-IMU-200',
          displayName: 'Fixture IMU',
          category: 'sensor',
        },
      },
      roleCategoryById: {
        role_compute: 'compute',
        role_sensor: 'sensor',
      },
    });

    expect(graph.nodes.length).toBeGreaterThan(0);
    expect(graph.edges.length).toBeGreaterThan(0);
    expect(graph.powerRails.length).toBeGreaterThan(0);
    for (const node of graph.nodes) {
      expect(resolveElectricalNodeRenderer(node.category)).toBeTruthy();
      expect(flowTypeForCategory(node.category)).toMatch(/^electrical-/);
    }
  });

  it('falls back to generic renderer for unknown categories', () => {
    expect(flowTypeForCategory('unknown')).toBe('electrical-generic');
    expect(resolveElectricalNodeRenderer('unknown').name).toBeTruthy();
  });
});

describe('simulation visual adapter', () => {
  it('maps provider preview without inventing fixture-specific wiring', () => {
    const graph = adaptSimulationVisualGraph({
      providerId: 'wokwi',
      surrogateUsed: true,
      mappings: [
        {
          providerPartId: 'esp',
          providerPartType: 'board-esp32-devkit-c-v4',
          mappingType: 'surrogate',
          pinProfile: [{ sourcePin: '21', providerPin: 'D21' }],
          sourceReferences: [
            {
              entityType: 'component-candidate',
              displayLabel: 'FX-MCU-32',
            },
          ],
        },
        {
          providerPartId: 'imu',
          providerPartType: 'wokwi-mpu6050',
          mappingType: 'surrogate',
          pinProfile: [{ sourcePin: 'SDA', providerPin: 'SDA' }],
          sourceReferences: [
            {
              entityType: 'component-candidate',
              displayLabel: 'FX-IMU-200',
            },
          ],
        },
      ],
      connections: [
        {
          id: 'c1',
          sourcePartId: 'esp',
          targetPartId: 'imu',
          sourcePin: 'D21',
          targetPin: 'SDA',
          label: 'I2C',
        },
      ],
      findings: [],
    });

    expect(graph.surrogateUsed).toBe(true);
    expect(graph.nodes).toHaveLength(2);
    expect(graph.connections).toHaveLength(1);
    expect(graph.nodes[0]?.nexusTitle).toBe('FX-MCU-32');
    expect(graph.nodes[0]?.mappingType).toBe('surrogate');
  });

  it('does not synthesize hardcoded golden wiring when connections are empty', () => {
    const graph = adaptSimulationVisualGraph({
      providerId: 'wokwi',
      surrogateUsed: true,
      mappings: [
        { providerPartId: 'esp', providerPartType: 'board-esp32-devkit-c-v4', mappingType: 'surrogate' },
        { providerPartId: 'imu', providerPartType: 'wokwi-mpu6050', mappingType: 'surrogate' },
      ],
      connections: [],
    });
    expect(graph.connections).toHaveLength(0);
  });
});
