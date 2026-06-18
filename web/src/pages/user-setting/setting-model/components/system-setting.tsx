import LLMLabel from '@/components/llm-select/llm-label';
import { ModelTreeSelect, ModelTypeMap } from '@/components/model-tree-select';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { FieldToModelType } from '@/constants/llm';
import { useTranslate } from '@/hooks/common-hooks';
import {
  useFetchDefaultModelDictionary,
  useSetDefaultModel,
} from '@/hooks/use-llm-request';
import { parseModelValue } from '@/utils/llm-util';
import { CircleQuestionMark } from 'lucide-react';
import { useCallback, useMemo } from 'react';

interface ModelFieldItemProps {
  id: string;
  label: string;
  value: string;
  tooltip?: string;
  isRequired?: boolean;
  onChange: (fieldId: string, value: string) => void;
}

function ModelFieldItem({
  label,
  value,
  tooltip,
  id,
  isRequired,
  onChange,
}: ModelFieldItemProps) {
  const { t } = useTranslate('setting');

  return (
    <div className="flex gap-3">
      <label className="block text-sm font-normal text-text-secondary mb-1 w-1/4">
        {isRequired && <span className="text-state-error">*</span>}
        {label}
        {tooltip && (
          <Tooltip>
            <TooltipContent>{tooltip}</TooltipContent>
            <TooltipTrigger>
              <CircleQuestionMark
                size={12}
                className="ml-1 text-text-secondary text-xs"
              />
            </TooltipTrigger>
          </Tooltip>
        )}
      </label>
      <div className="w-3/4">
        <ModelTreeSelect
          modelTypes={ModelTypeMap[id as keyof typeof ModelTypeMap] ?? ['chat']}
          value={value}
          placeholder={t('selectModelPlaceholder')}
          showSearch
          allowClear={false}
          onChange={(value) => onChange(id, value)}
          renderSelected={value ? () => <LLMLabel value={value} /> : undefined}
        />
      </div>
    </div>
  );
}

function SystemSetting() {
  const { t } = useTranslate('setting');
  const defaultModelDictionary = useFetchDefaultModelDictionary();
  const { setDefaultModel } = useSetDefaultModel();

  const handleModelChange = useCallback(
    (fieldId: string, value: string) => {
      const model = parseModelValue(value);
      if (!model) return;

      setDefaultModel({
        model_provider: model.model_provider,
        model_instance: model.model_instance,
        model_type: FieldToModelType[fieldId],
        model_name: model.model_name,
      });
    },
    [setDefaultModel],
  );

  const llmList = useMemo(() => {
    return [
      {
        id: 'llm_id',
        label: t('chatModel'),
        isRequired: true,
        value: defaultModelDictionary.llm_id,
        tooltip: t('chatModelTip'),
      },
      {
        id: 'embd_id',
        label: t('embeddingModel'),
        value: defaultModelDictionary.embd_id,
        tooltip: t('embeddingModelTip'),
      },
      {
        id: 'img2txt_id',
        label: t('img2txtModel'),
        value: defaultModelDictionary.img2txt_id,
        tooltip: t('img2txtModelTip'),
      },
      {
        id: 'asr_id',
        label: t('sequence2txtModel'),
        value: defaultModelDictionary.asr_id,
        tooltip: t('sequence2txtModelTip'),
      },
      {
        id: 'rerank_id',
        label: t('rerankModel'),
        value: defaultModelDictionary.rerank_id,
        tooltip: t('rerankModelTip'),
      },
      {
        id: 'tts_id',
        label: t('ttsModel'),
        value: defaultModelDictionary.tts_id,
        tooltip: t('ttsModelTip'),
      },
    ];
  }, [defaultModelDictionary, t]);

  return (
    <article className="rounded-lg w-full">
      <header className="py-5">
        <h2 className="text-2xl font-medium text-text-primary">
          {t('systemModelSettings')}
        </h2>
        <p className="mt-1 text-sm text-text-secondary ">
          {t('systemModelDescription')}
        </p>
      </header>

      <div className="px-7 py-6 space-y-6 max-h-[70vh] overflow-y-auto border border-border-button rounded-lg">
        {llmList.map((item) => (
          <ModelFieldItem
            key={item.id}
            {...item}
            onChange={handleModelChange}
          />
        ))}
      </div>
    </article>
  );
}

export default SystemSetting;
