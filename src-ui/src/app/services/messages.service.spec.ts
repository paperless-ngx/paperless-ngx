import { TestBed } from '@angular/core/testing'

import { DjangoMessageLevel, MessagesService } from './messages.service'

import { environment } from 'src/environments/environment'

const messages = [
  { level: DjangoMessageLevel.ERROR, message: 'Error Message' },
  { level: DjangoMessageLevel.INFO, message: 'Info Message' },
]

describe('MessagesService', () => {
  let service: MessagesService

  beforeEach(() => {
    window['DJANGO_MESSAGES'] = messages
    TestBed.configureTestingModule({
      providers: [MessagesService],
    })
    service = TestBed.inject(MessagesService)
  })

  it('calls retrieves global django messages if present', () => {
    expect(service.get()).toEqual(messages)

    window['DJANGO_MESSAGES'] = undefined
    expect(service.get()).toEqual([])
  })
})
