export interface ExistingSource {
  id: number;
  title: string;
  link_url?: string;
}

export interface OutputContent {
  id: number;
  title: string;
  audio_url: string;
  script_url: string;
  created_at?: string;
  summary: string;
}
