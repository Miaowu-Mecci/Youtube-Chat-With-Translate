export function getTimeTextHourMin(time) {
  return time instanceof Date && !isNaN(time) ? time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : ''
}
export const formatCurrency = value => Number(value).toFixed(2)
