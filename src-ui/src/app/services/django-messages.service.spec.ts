import { TestBed } from '@angular/core/testing'

import {
  DjangoMessageLevel,
  DjangoMessagesService,
} from './django-messages.service'

const messages = [
  { level: DjangoMessageLevel.ERROR, message: 'Error Message' },
  { level: DjangoMessageLevel.INFO, message: 'Info Message' },
]

describe('DjangoMessagesService', () => {
  let service: DjangoMessagesService

  beforeEach(() => {
    window['DJANGO_MESSAGES'] = messages
    TestBed.configureTestingModule({
      providers: [DjangoMessagesService],
    })
    service = TestBed.inject(DjangoMessagesService)
  })

  it('should retrieve global django messages if present', () => {
    expect(service.get()).toEqual(messages)

    window['DJANGO_MESSAGES'] = undefined
    expect(service.get()).toEqual([])
  })
})
