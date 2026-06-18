export const mapModelKey = {
  image2text: 'VLM',
  speech2text: 'ASR',
  chat: 'LLM',
  vision: 'VLM',
  embedding: 'Embedding',
  asr: 'ASR',
  rerank: 'Rerank',
  tts: 'TTS',
  ocr: 'OCR',
};

export type AvailableModelsProps = {
  handleAddModel: (factory: string) => void;
};

export const AvailableModels = (_props: AvailableModelsProps) => null;
