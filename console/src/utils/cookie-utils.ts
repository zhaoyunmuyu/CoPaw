export function getTargetCookie(cookieName: string) {
  return document.cookie.split("; ").find((item) => item.startsWith(cookieName + "="))?.split("=")[1];
}
