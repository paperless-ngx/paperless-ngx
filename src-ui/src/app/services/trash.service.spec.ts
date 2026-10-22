import { TestBed } from '@angular/core/testing'

import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'
import { DocumentListViewService } from './document-list-view.service'
import { Toast, ToastService } from './toast.service'
import { TrashService } from './trash.service'

describe('TrashService', () => {
  let service: TrashService
  let httpTestingController: HttpTestingController
  let toastService: ToastService
  let documentListViewService: DocumentListViewService

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    })
    service = TestBed.inject(TrashService)
    httpTestingController = TestBed.inject(HttpTestingController)
    toastService = TestBed.inject(ToastService)
    documentListViewService = TestBed.inject(DocumentListViewService)
  })

  it('should call correct endpoint for getTrash', () => {
    service.getTrash().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/?page=1`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should call correct endpoint for emptyTrash', () => {
    service.emptyTrash().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({ action: 'empty' })

    service.emptyTrash([1, 2, 3]).subscribe()
    const req2 = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/`
    )
    expect(req2.request.body).toEqual({
      action: 'empty',
      documents: [1, 2, 3],
    })
  })

  it('should call correct endpoint for restoreDocuments', () => {
    service.restoreDocuments([1, 2, 3]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      action: 'restore',
      documents: [1, 2, 3],
    })
  })

  it('should show a persistent moved to trash toast with undo', () => {
    let toasts: Toast[] = []
    toastService.getToasts().subscribe((t) => (toasts = [...t]))
    const reloadSpy = jest
      .spyOn(documentListViewService, 'reload')
      .mockImplementation(() => {})

    service.notifyMovedToTrash('Moved 2 document(s) to the trash', [1, 2])
    expect(toasts).toHaveLength(1)
    expect(toasts[0].actionName).toEqual('Undo')

    toasts[0].action()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/`
    )
    expect(req.request.body).toEqual({ action: 'restore', documents: [1, 2] })
    req.flush('OK')
    expect(reloadSpy).toHaveBeenCalled()
    expect(toasts[0].content).toEqual('Document(s) restored')
  })

  it('should show an error if undo fails', () => {
    let toast: Toast
    toastService.getToasts().subscribe((t) => (toast = t[0]))
    const errorSpy = jest.spyOn(toastService, 'showError')

    service.notifyMovedToTrash('Moved "Invoice" to the trash', [1])
    toast.action()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}trash/`)
      .flush('error', { status: 500, statusText: 'Server Error' })
    expect(errorSpy).toHaveBeenCalled()
  })

  it('should not offer undo without document ids', () => {
    let toast: Toast
    toastService.getToasts().subscribe((t) => (toast = t[0]))

    service.notifyMovedToTrash('Moved 500 document(s) to the trash')
    expect(toast.content).toEqual('Moved 500 document(s) to the trash')
    expect(toast.action).toBeUndefined()
  })
})
