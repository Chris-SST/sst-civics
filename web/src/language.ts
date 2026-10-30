import { LANGUAGES } from "./i18n";

/** Switch the interface to the API language `code` if a locale file exists for it;
 * otherwise the interface stays as it is and English fills any gaps. */
export function switchInterface(code: string, changeLanguage: (lng: string) => unknown): void {
  const match = LANGUAGES.find((l) => l.short === code);
  if (match) void changeLanguage(match.code);
}
