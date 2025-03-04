import { ComponentFixture, TestBed } from '@angular/core/testing'

import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ToastService } from 'src/app/services/toast.service'
import { EmailDocumentDialogComponent } from './email-document-dialog.component'

describe('EmailDocumentDialogComponent', () => {
  let component: EmailDocumentDialogComponent
  let fixture: ComponentFixture<EmailDocumentDialogComponent>
  let documentService: DocumentService
  let permissionsService: PermissionsService
  let toastService: ToastService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        EmailDocumentDialogComponent,
        IfPermissionsDirective,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        NgbActiveModal,
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(EmailDocumentDialogComponent)
    documentService = TestBed.inject(DocumentService)
    toastService = TestBed.inject(ToastService)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should set hasArchiveVersion and useArchiveVersion', () => {
    expect(component.hasArchiveVersion).toBeTruthy()
    component.hasArchiveVersion = false
    expect(component.hasArchiveVersion).toBeFalsy()
    expect(component.useArchiveVersion).toBeFalsy()
  })

  it('should support sending document via email, showing error if needed', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastSuccessSpy = jest.spyOn(toastService, 'showInfo')
    component.emailAddress = 'hello@paperless-ngx.com'
    component.emailSubject = 'Hello'
    component.emailMessage = 'World'
    jest
      .spyOn(documentService, 'emailDocument')
      .mockReturnValue(throwError(() => new Error('Unable to email document')))
    component.emailDocument()
    expect(toastErrorSpy).toHaveBeenCalled()

    jest.spyOn(documentService, 'emailDocument').mockReturnValue(of(true))
    component.emailDocument()
    expect(toastSuccessSpy).toHaveBeenCalled()
  })

  it('should close the dialog', () => {
    const activeModal = TestBed.inject(NgbActiveModal)
    const closeSpy = jest.spyOn(activeModal, 'close')
    component.close()
    expect(closeSpy).toHaveBeenCalled()
  })
})
