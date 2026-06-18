import Spotlight from '@/components/spotlight';
import SystemSetting from './components/system-setting';

const ModelProviders = () => {
  return (
    <div className="flex w-full border-[0.5px] border-border-button rounded-lg relative ">
      <Spotlight />
      <section className="flex flex-col gap-4 w-full px-5 overflow-auto scrollbar-auto">
        <SystemSetting />
      </section>
    </div>
  );
};

export default ModelProviders;
