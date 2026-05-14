import React, { useState } from 'react';

interface DiscoveryAnswers {
  effect_type?: string;
  shape_type?: string;
  background_constraint?: string;
  animation_type?: string;
}

interface VFXDiscoveryFormProps {
  onSubmit: (answers: DiscoveryAnswers) => void;
  onCancel?: () => void;
}

const VFXDiscoveryForm: React.FC<VFXDiscoveryFormProps> = ({ onSubmit, onCancel }) => {
  const [answers, setAnswers] = useState<DiscoveryAnswers>({});
  
  const effectTypes = [
    { id: 'ripple', label: '涟漪扩散', token: '{effect.ripple}' },
    { id: 'glow', label: '光晕效果', token: '{effect.glow}' },
    { id: 'gradient', label: '渐变背景', token: '{effect.gradient}' },
    { id: 'frosted', label: '磨砂玻璃', token: '{effect.frosted}' },
    { id: 'flow', label: '流光效果', token: '{effect.flow}' },
  ];
  
  const shapeTypes = [
    { id: 'circle', label: '圆形', token: '{sdf.circle}' },
    { id: 'box', label: '矩形', token: '{sdf.box}' },
    { id: 'rounded_box', label: '圆角矩形', token: '{sdf.rounded_box}' },
    { id: 'ring', label: '环形', token: '{sdf.ring}' },
  ];
  
  const backgroundConstraints = [
    { id: 'white_strict', label: '纯白背景', token: '{bg.white_strict}' },
    { id: 'black_strict', label: '纯黑背景', token: '{bg.black_strict}' },
    { id: 'gradient', label: '渐变背景', token: '{bg.gradient}' },
    { id: 'flexible', label: '灵活背景', token: '{bg.flexible}' },
  ];
  
  const animationTypes = [
    { id: 'expand_3s', label: '扩散 3s', token: '{anim.expand_3s}' },
    { id: 'expand_4s', label: '扩散 4s', token: '{anim.expand_4s}' },
    { id: 'pulse_2s', label: '脉冲 2s', token: '{anim.pulse_2s}' },
    { id: 'flow', label: '流光', token: '{anim.flow}' },
    { id: 'static', label: '静态', token: '{anim.static}' },
  ];
  
  const handleConfirm = () => {
    onSubmit(answers);
  };
  
  return (
    <div className="vfx-discovery-form p-4 bg-gray-50 rounded-lg border border-gray-200">
      <h3 className="text-lg font-semibold mb-4 text-gray-800">
        快速选择效果方向
      </h3>
      <p className="text-sm text-gray-600 mb-4">
        选择以下选项帮助 Agent 更准确理解意图（可选）
      </p>
      
      {/* Effect Type */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          效果类型
        </label>
        <div className="flex gap-2 flex-wrap">
          {effectTypes.map(et => (
            <button
              key={et.id}
              onClick={() => setAnswers({ ...answers, effect_type: et.token })}
              className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                answers.effect_type === et.token
                  ? 'bg-blue-100 border-blue-500 text-blue-700'
                  : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              {et.label}
            </button>
          ))}
        </div>
      </div>
      
      {/* Shape Type */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          主体形状
        </label>
        <div className="flex gap-2 flex-wrap">
          {shapeTypes.map(st => (
            <button
              key={st.id}
              onClick={() => setAnswers({ ...answers, shape_type: st.token })}
              className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                answers.shape_type === st.token
                  ? 'bg-green-100 border-green-500 text-green-700'
                  : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              {st.label}
            </button>
          ))}
        </div>
      </div>
      
      {/* Background Constraint */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          背景约束
        </label>
        <div className="flex gap-2 flex-wrap">
          {backgroundConstraints.map(bg => (
            <button
              key={bg.id}
              onClick={() => setAnswers({ ...answers, background_constraint: bg.token })}
              className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                answers.background_constraint === bg.token
                  ? 'bg-yellow-100 border-yellow-500 text-yellow-700'
                  : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              {bg.label}
            </button>
          ))}
        </div>
      </div>
      
      {/* Animation Type */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          动画类型
        </label>
        <div className="flex gap-2 flex-wrap">
          {animationTypes.map(at => (
            <button
              key={at.id}
              onClick={() => setAnswers({ ...answers, animation_type: at.token })}
              className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                answers.animation_type === at.token
                  ? 'bg-purple-100 border-purple-500 text-purple-700'
                  : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              {at.label}
            </button>
          ))}
        </div>
      </div>
      
      {/* Actions */}
      <div className="flex gap-2 mt-6">
        <button
          onClick={handleConfirm}
          disabled={!answers.effect_type}
          className={`px-4 py-2 rounded-md font-medium transition-colors ${
            answers.effect_type
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
        >
          确认选择
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-md bg-gray-200 text-gray-700 hover:bg-gray-300 font-medium"
          >
            取消
          </button>
        )}
      </div>
      
      {/* Preview */}
      {answers.effect_type && (
        <div className="mt-4 p-3 bg-white rounded border border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">已选择</h4>
          <div className="text-xs text-gray-600 space-y-1">
            {answers.effect_type && (
              <p>• 效果: <span className="text-blue-600">{answers.effect_type}</span></p>
            )}
            {answers.shape_type && (
              <p>• 形状: <span className="text-green-600">{answers.shape_type}</span></p>
            )}
            {answers.background_constraint && (
              <p>• 背景: <span className="text-yellow-600">{answers.background_constraint}</span></p>
            )}
            {answers.animation_type && (
              <p>• 动画: <span className="text-purple-600">{answers.animation_type}</span></p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default VFXDiscoveryForm;