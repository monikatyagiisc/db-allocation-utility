import type { DatabaseSortField } from './api';

export type DatabaseFieldConfig = {
  key: DatabaseSortField;
  label: string;
  type?: 'number' | 'date';
  wide?: boolean;
  headerTitle?: string;
};

export const DATABASE_FIELDS: DatabaseFieldConfig[] = [
  {
    key: 'serial_number',
    label: 'Sheet row #',
    type: 'number',
    headerTitle: 'Row number from the Excel sheet (not the database record ID)',
  },
  { key: 'database_type', label: 'Type' },
  { key: 'database_name', label: 'Database' },
  {
    key: 'cics_transactions',
    label: '# CICS Trns',
    type: 'number',
    headerTitle: '# of CICS Trns',
  },
  { key: 'prod_mirror', label: 'Prod Mirror' },
  { key: 'release', label: 'Release' },
  { key: 'lifecycle', label: 'Lifecycle' },
  { key: 'status', label: 'Status' },
  { key: 'assignee', label: 'Assignee' },
  { key: 'team', label: 'Team' },
  { key: 'project', label: 'Project' },
  { key: 'start_date', label: 'Start Date', type: 'date' },
  { key: 'end_date', label: 'End Date', type: 'date' },
  {
    key: 'can_be_released',
    label: 'Can release',
    headerTitle: 'Can be released -Y/N',
  },
  { key: 'comments', label: 'Comments', wide: true },
];
