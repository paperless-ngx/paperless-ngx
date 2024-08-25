import { Injectable } from '@angular/core'

// see https://docs.djangoproject.com/en/5.0/ref/contrib/messages/#message-tags
export enum DjangoMessageLevel {
  DEBUG = 'debug',
  INFO = 'info',
  SUCCESS = 'success',
  WARNING = 'warning',
  ERROR = 'error',
}

export interface DjangoMessage {
  level: DjangoMessageLevel
  message: string
}

@Injectable({
  providedIn: 'root',
})
export class DjangoMessagesService {
  constructor() {}

  get(): DjangoMessage[] {
    // These are embedded in the HTML as raw JS, the service is for convenience
    return window['DJANGO_MESSAGES'] ?? []
  }
}
