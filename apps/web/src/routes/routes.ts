/**
 * The tool routes from the mockup's sidebar, and the milestone each is built in.
 *
 * Shown as placeholders until their milestone lands. Being explicit about *when* a tool
 * arrives is more useful than hiding it — the nav is also the roadmap.
 */

export interface ToolRoute {
  path: string;
  label: string;
  kicker: string;
  description: string;
  milestone: string;
  requirements: string[];
  section: 'tools' | 'assessment';
  icon: 'monitor' | 'scope' | 'drift' | 'checklist' | 'export';
}

export const TOOL_ROUTES: ToolRoute[] = [
  {
    path: '/monitor',
    label: 'Payment Page Monitor',
    kicker: 'Tool 01',
    description:
      'Crawls checkout, inventories every script and its integrity attribute, and emits a dated evidence artifact on change.',
    milestone: 'M2',
    requirements: ['6.4.3', '11.6.1'],
    section: 'tools',
    icon: 'monitor',
  },
  {
    path: '/scope',
    label: 'Scope Map',
    kicker: 'Tool 02',
    description:
      'Maps the cardholder data environment and the business around it, with evidence still outstanding drawn on each zone.',
    milestone: 'M4',
    requirements: ['12.5.2'],
    section: 'tools',
    icon: 'scope',
  },
  {
    path: '/drift',
    label: 'Scope Drift Detector',
    kicker: 'Tool 03',
    description:
      'Compares declared scope against the observed environment and returns the contradictions as findings.',
    milestone: 'M5',
    requirements: ['12.5.2', '11.4.5', '1.4.2'],
    section: 'tools',
    icon: 'drift',
  },
  {
    path: '/checklist',
    label: 'PCI Checklist',
    kicker: 'Tool 04',
    description:
      'Reads what you have attached and tells you what is still needed, requirement by requirement.',
    milestone: 'M3',
    requirements: ['all'],
    section: 'tools',
    icon: 'checklist',
  },
  {
    path: '/export',
    label: 'ROC Export',
    kicker: 'Assessment',
    description:
      'Assembles the Report on Compliance, the Attestation of Compliance and every attached artifact into one dated archive.',
    milestone: 'M6',
    requirements: [],
    section: 'assessment',
    icon: 'export',
  },
];
