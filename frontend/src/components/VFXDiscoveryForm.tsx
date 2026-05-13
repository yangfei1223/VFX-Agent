import React, { useState } from 'react';

interface DiscoveryAnswers {
  effect_type?: string;
  shape_type?: string;
  animation_type?: string;
  background_constraint?: string;
}

interface VFXDiscoveryFormProps {
  onSubmit: (answers: DiscoveryAnswers) => void;
  onClose?: () => void;
}

const VFXDiscoveryForm: React.FC<VFXDiscoveryFormProps> = ({ onSubmit, onClose }) => {
  const [answers, setAnswers] = useState<DiscoveryAnswers>({});
  const [step, setStep] = useState(1);

  const effectTypes = [
    { id: 'ripple', label: '涟漪扩散', desc: '圆形扩散效果' },
    { id: 'glow', label: '光晕效果', desc: '柔和发光效果' },
    { id: 'gradient', label: '渐变背景', desc: '颜色渐变效果' },
    { id: 'frosted', label: '磨砂玻璃', desc: '模糊+噪声效果' },
    { id: 'flow', label: '流光效果', desc: '动态流光效果' },
    { id: 'particle_dots', label: '点粒子', desc: '粒子散射效果' },
    { id: 'sparkle', label: '闪烁星光', desc: '高光闪烁效果' },
  ];

  const shapeTypes = [
    { id: 'circle', label: '圆形' },
    { id: 'rect', label: '矩形' },
    { id: 'hexagon', label: '六边形' },
    { id: 'star', label: '星形' },
    { id: 'none', label: '全屏效果' },
  ];

  const animationTypes = [
    { id: 'expand', label: '扩散 (3-4s)' },
    { id: 'pulse', label: '脉冲 (2s)' },
    { id: 'flow', label: '流动 (∞)' },
    { id: 'static', label: '静态' },
  ];

  const backgroundConstraints = [
    { id: 'white_strict', label: '纯白背景 (RGB误差<0.05)' },
    { id: 'black_strict', label: '纯黑背景 (RGB误差<0.05)' },
    { id: 'gradient', label: '渐变背景' },
    { id: 'flexible', label: '灵活背景' },
  ];

  const handleSelect = (key: keyof DiscoveryAnswers, value: string) => {
    setAnswers({ ...answers, [key]: value });
    if (step < 4) setStep(step + 1);
  };

  const handleSubmit = () => {
    onSubmit(answers);
    onClose?.();
  };

  const isComplete = answers.effect_type && answers.shape_type && answers.animation_type && answers.background_constraint;

  return (
    <div className="discovery-form p-4 bg-white rounded-lg shadow-lg max-w-md">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">快速选择效果方向</h3>
        {onClose && (
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            ✕
          </button>
        )}
      </div>

      {/* Progress indicator */}
      <div className="flex gap-2 mb-4">
        {[1, 2, 3, 4].map((s) => (
          <div
            key={s}
            className={`w-8 h-2 rounded ${
              s <= step ? 'bg-blue-500' : 'bg-gray-200'
            }`}
          />
        ))}
      </div>

      {/* Step 1: Effect Type */}
      {step === 1 && (
        <div>
          <p className="text-sm text-gray-600 mb-2">Step 1: 效果类型</p>
          <div className="grid grid-cols-2 gap-2">
            {effectTypes.map((et) => (
              <button
                key={et.id}
                onClick={() => handleSelect('effect_type', et.id)}
                className={`p-3 rounded border text-left ${
                  answers.effect_type === et.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-blue-300'
                }`}
              >
                <div className="font-medium">{et.label}</div>
                <div className="text-xs text-gray-500">{et.desc}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 2: Shape Type */}
      {step === 2 && (
        <div>
          <p className="text-sm text-gray-600 mb-2">Step 2: 主体形状</p>
          <div className="grid grid-cols-3 gap-2">
            {shapeTypes.map((st) => (
              <button
                key={st.id}
                onClick={() => handleSelect('shape_type', st.id)}
                className={`p-2 rounded border ${
                  answers.shape_type === st.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-blue-300'
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: Animation Type */}
      {step === 3 && (
        <div>
          <p className="text-sm text-gray-600 mb-2">Step 3: 动画类型</p>
          <div className="grid grid-cols-2 gap-2">
            {animationTypes.map((at) => (
              <button
                key={at.id}
                onClick={() => handleSelect('animation_type', at.id)}
                className={`p-2 rounded border ${
                  answers.animation_type === at.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-blue-300'
                }`}
              >
                {at.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 4: Background Constraint */}
      {step === 4 && (
        <div>
          <p className="text-sm text-gray-600 mb-2">Step 4: 背景约束</p>
          <div className="grid grid-cols-2 gap-2">
            {backgroundConstraints.map((bc) => (
              <button
                key={bc.id}
                onClick={() => handleSelect('background_constraint', bc.id)}
                className={`p-2 rounded border ${
                  answers.background_constraint === bc.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-blue-300'
                }`}
              >
                {bc.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Submit button */}
      {isComplete && (
        <button
          onClick={handleSubmit}
          className="mt-4 w-full py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          确认选择
        </button>
      )}

      {/* Back button */}
      {step > 1 && (
        <button
          onClick={() => setStep(step - 1)}
          className="mt-2 text-sm text-gray-500 hover:text-gray-700"
        >
          ← 返回上一步
        </button>
      )}
    </div>
  );
};

export default VFXDiscoveryForm;