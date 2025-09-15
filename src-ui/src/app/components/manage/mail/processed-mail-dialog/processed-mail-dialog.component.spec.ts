import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ProcessedMailDialogComponent } from './processed-mail-dialog.component'

describe('ProcessedMailDialogComponent', () => {
  let component: ProcessedMailDialogComponent
  let fixture: ComponentFixture<ProcessedMailDialogComponent>
  let httpTestingController: HttpTestingController
  let toastService: ToastService

  const rule: any = { id: 10, name: 'Mail Rule' } // minimal rule object for tests
  const mails = [
    {
      id: 1,
      rule: rule.id,
      folder: 'INBOX',
      uid: 111,
      subject: 'A',
      received: new Date().toISOString(),
      processed: new Date().toISOString(),
      status: 'SUCCESS',
      error: null,
    },
    {
      id: 2,
      rule: rule.id,
      folder: 'INBOX',
      uid: 222,
      subject: 'B',
      received: new Date().toISOString(),
      processed: new Date().toISOString(),
      status: 'FAILED',
      error: 'Oops',
    },
  ]

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        ProcessedMailDialogComponent,
        FormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        DatePipe,
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    httpTestingController = TestBed.inject(HttpTestingController)
    toastService = TestBed.inject(ToastService)
    fixture = TestBed.createComponent(ProcessedMailDialogComponent)
    component = fixture.componentInstance
    component.rule = rule
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  function expectListRequest(ruleId: number) {
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}processed_mail/?page=1&page_size=50&ordering=-processed_at&rule=${ruleId}`
    )
    expect(req.request.method).toEqual('GET')
    return req
  }

  it('should load processed mails on init', () => {
    fixture.detectChanges()
    const req = expectListRequest(rule.id)
    req.flush({ count: 2, results: mails })
    expect(component.loading).toBeFalsy()
    expect(component.processedMails).toEqual(mails)
  })

  it('should delete selected mails and reload', () => {
    fixture.detectChanges()
    // initial load
    const initialReq = expectListRequest(rule.id)
    initialReq.flush({ count: 0, results: [] })

    // select a couple of mails and delete
    component.selectedMailIds.add(5)
    component.selectedMailIds.add(6)
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    component.deleteSelected()

    const delReq = httpTestingController.expectOne(
      `${environment.apiBaseUrl}processed_mail/bulk_delete/`
    )
    expect(delReq.request.method).toEqual('POST')
    expect(delReq.request.body).toEqual({ mail_ids: [5, 6] })
    delReq.flush({})

    // reload after delete
    const reloadReq = expectListRequest(rule.id)
    reloadReq.flush({ count: 0, results: [] })
    expect(toastInfoSpy).toHaveBeenCalled()
  })

  it('should toggle all, toggle selected, and clear selection', () => {
    fixture.detectChanges()
    // initial load with two mails
    const req = expectListRequest(rule.id)
    req.flush({ count: 2, results: mails })
    fixture.detectChanges()

    // toggle all via header checkbox
    const inputs = fixture.debugElement.queryAll(
      By.css('input.form-check-input')
    )
    const header = inputs[0].nativeElement as HTMLInputElement
    header.dispatchEvent(new Event('click'))
    header.checked = true
    header.dispatchEvent(new Event('click'))
    expect(component.selectedMailIds.size).toEqual(mails.length)

    // toggle a single mail
    component.toggleSelected(mails[0] as any)
    expect(component.selectedMailIds.has(mails[0].id)).toBeFalsy()
    component.toggleSelected(mails[0] as any)
    expect(component.selectedMailIds.has(mails[0].id)).toBeTruthy()

    // clear selection
    component.clearSelection()
    expect(component.selectedMailIds.size).toEqual(0)
    expect(component.toggleAllEnabled).toBeFalsy()
  })

  it('should close the dialog', () => {
    const activeModal = TestBed.inject(NgbActiveModal)
    const closeSpy = jest.spyOn(activeModal, 'close')
    component.close()
    expect(closeSpy).toHaveBeenCalled()
  })
})
