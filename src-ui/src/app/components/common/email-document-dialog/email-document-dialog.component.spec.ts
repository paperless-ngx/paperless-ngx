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
    component.documentIds = [1]
    fixture.detectChanges()
  })

  it('should set hasArchiveVersion and useArchiveVersion', () => {
    expect(component.hasArchiveVersion).toBeTruthy()
    expect(component.useArchiveVersion).toBeTruthy()

    component.hasArchiveVersion = false
    expect(component.hasArchiveVersion).toBeFalsy()
    expect(component.useArchiveVersion).toBeFalsy()
  })

  it('should support sending single document via email, showing error if needed', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastSuccessSpy = jest.spyOn(toastService, 'showInfo')
    component.documentIds = [1]
    component.emailAddress = 'hello@paperless-ngx.com'
    component.emailSubject = 'Hello'
    component.emailMessage = 'World'
    jest
      .spyOn(documentService, 'emailDocuments')
      .mockReturnValue(throwError(() => new Error('Unable to email document')))
    component.emailDocuments()
    expect(toastErrorSpy).toHaveBeenCalledWith(
      'Error emailing document',
      expect.any(Error)
    )

    jest.spyOn(documentService, 'emailDocuments').mockReturnValue(of(true))
    component.emailDocuments()
    expect(toastSuccessSpy).toHaveBeenCalledWith('Email sent')
  })

  it('should support sending multiple documents via email, showing appropriate messages', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastSuccessSpy = jest.spyOn(toastService, 'showInfo')
    component.documentIds = [1, 2, 3]
    component.emailAddress = 'hello@paperless-ngx.com'
    component.emailSubject = 'Hello'
    component.emailMessage = 'World'
    jest
      .spyOn(documentService, 'emailDocuments')
      .mockReturnValue(throwError(() => new Error('Unable to email documents')))
    component.emailDocuments()
    expect(toastErrorSpy).toHaveBeenCalledWith(
      'Error emailing documents',
      expect.any(Error)
    )

    jest.spyOn(documentService, 'emailDocuments').mockReturnValue(of(true))
    component.emailDocuments()
    expect(toastSuccessSpy).toHaveBeenCalledWith('Email sent')
  })

  it('should close the dialog', () => {
    const activeModal = TestBed.inject(NgbActiveModal)
    const closeSpy = jest.spyOn(activeModal, 'close')
    component.close()
    expect(closeSpy).toHaveBeenCalled()
  })
})
