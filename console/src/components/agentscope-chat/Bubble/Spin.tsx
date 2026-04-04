import { useProviderContext } from '@/components/agentscope-chat';

export default function () {
  const { getPrefixCls } = useProviderContext();
  const prefixCls = getPrefixCls('bubble-loading');

  return <div className={prefixCls} >
    <div className={`${prefixCls}-dot1`} />
    <div className={`${prefixCls}-dot2`} />
    <div className={`${prefixCls}-dot3`} />
    <div className={`${prefixCls}-text`}>-</div>
  </div>
}