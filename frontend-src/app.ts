type ApiProfile = {
  id: string;
  name?: string;
  endpoint?: string;
  apiKey?: string;
  mode?: string;
  availableModels?: string[];
  models?: Record<string, string>;
};

type BlogSummary = {
  id: string;
  title?: string;
  groupId?: string;
  groupName?: string;
  versionIndex?: number;
  versionLabel?: string;
  createdAt?: string;
  score?: number | string;
  productType?: string;
  tags?: string[];
};

type IterationRound = {
  round: number;
  score?: number | string;
  article?: string;
  articleAfter?: string;
  evaluation?: Record<string, unknown>;
  modification?: Record<string, unknown>;
  diff?: Record<string, unknown>;
};

type IterationResult = {
  rounds?: IterationRound[];
  finalArticle?: string;
  finalEvaluation?: Record<string, unknown>;
  inProgress?: boolean;
};

export type { ApiProfile, BlogSummary, IterationResult, IterationRound };
