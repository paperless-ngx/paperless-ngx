export enum InstallType {
  Containerized = 'containerized',
  BareMetal = 'bare-metal',
}

export interface SystemStorageStatus {
  'total': number,
  'available': number,
  'used': number,
  'backup': number,
  'document': number,
  'another': number
}
