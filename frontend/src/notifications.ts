// Evento simples para o menu atualizar o contador de não lidas
const EVENT = "pt:notifications";

export function notifyUnreadChanged() {
  window.dispatchEvent(new Event(EVENT));
}

export function onUnreadChanged(fn: () => void) {
  window.addEventListener(EVENT, fn);
  return () => window.removeEventListener(EVENT, fn);
}
