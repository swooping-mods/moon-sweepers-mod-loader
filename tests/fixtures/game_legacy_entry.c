/* Deliberately has the runtime marker, but no v8 entry. Never reinterpret it. */
int MoonLab_ModStart(void *domain,void *module){(void)domain;(void)module;return 1;}
int MoonLab_RuntimeServicesAbi(void){return 1;}
