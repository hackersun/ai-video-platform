export type RecoveryAction = { code: string; label: string };

export type RecoveryOperation = {
  operation_id: string;
  capability: string;
  stage: string;
  operation_status: string;
  title: string;
  message: string;
  cost_state: string;
  safe_retry: boolean;
  retry_requires_confirmation: boolean;
  retry_scope: string | null;
  actions: RecoveryAction[];
};

export type SeriesRunRecovery = {
  run_id: string;
  run_version: number;
  blocked: boolean;
  operations: RecoveryOperation[];
  preserved_artifacts: Array<{ kind: string; asset_id?: string | null; message: string }>;
};

export type RecoveryAcknowledgement = {
  acknowledged: boolean;
  action_code: string;
  operation_id: string;
  retry_scope: string | null;
  requires_provider_submission: boolean;
  next_action: string;
};
