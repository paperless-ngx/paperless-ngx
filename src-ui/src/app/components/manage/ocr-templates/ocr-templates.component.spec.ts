import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { NgbModal, NgbModalRef } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { OcrTemplate } from 'src/app/data/ocr-template'
import { User } from 'src/app/data/user'
import { DirtyFormGuard } from 'src/app/guards/dirty-form.guard'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { UserService } from 'src/app/services/rest/user.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { OcrTemplateEditorComponent } from './ocr-template-editor/ocr-template-editor.component'
import { OcrTemplatesComponent } from './ocr-templates.component'

const templates: OcrTemplate[] = [
  {
    id: 1,
    name: 'Invoices',
    document_type: 2,
    sample_document: null,
    source_width: 0,
    source_height: 0,
    enabled: true,
    zones: [],
  },
]

describe('OcrTemplatesComponent', () => {
  let component: OcrTemplatesComponent
  let fixture: ComponentFixture<OcrTemplatesComponent>
  let ocrTemplateService: OcrTemplateService
  let modalService: NgbModal
  let toastService: ToastService
  let modal: NgbModalRef

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [NgxBootstrapIconsModule.pick(allIcons), OcrTemplatesComponent],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    TestBed.inject(PermissionsService).initialize(
      [
        'view_ocrtemplate',
        'add_ocrtemplate',
        'change_ocrtemplate',
        'delete_ocrtemplate',
      ],
      { id: 1, groups: [], is_superuser: false } as User
    )
    jest
      .spyOn(TestBed.inject(UserService), 'listAll')
      .mockReturnValue(of({ count: 0, all: [], results: [] }))

    ocrTemplateService = TestBed.inject(OcrTemplateService)
    jest
      .spyOn(ocrTemplateService, 'listAll')
      .mockReturnValue(of({ count: 1, all: [1], results: templates }))
    jest
      .spyOn(TestBed.inject(DocumentTypeService), 'listAll')
      .mockReturnValue(
        of({ count: 1, all: [2], results: [{ id: 2, name: 'Invoice' }] })
      )
    modalService = TestBed.inject(NgbModal)
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    toastService = TestBed.inject(ToastService)
    fixture = TestBed.createComponent(OcrTemplatesComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  afterEach(() => modalService.dismissAll())

  it('should show templates with their document type', () => {
    const text = fixture.nativeElement.textContent
    expect(text).toContain('Invoices')
    expect(text).toContain('Invoice')
  })

  it.each([
    {
      name: 'owned',
      owner: 1,
      user_can_change: true,
      editable: true,
      deletable: true,
    },
    {
      name: 'unowned',
      owner: null,
      user_can_change: true,
      editable: true,
      deletable: true,
    },
    {
      name: 'view-only shared',
      owner: 2,
      user_can_change: false,
      editable: false,
      deletable: false,
    },
    {
      name: 'editable shared',
      owner: 2,
      user_can_change: true,
      editable: true,
      deletable: false,
    },
  ])(
    'should respect permissions for $name templates',
    async ({ owner, user_can_change, editable, deletable }) => {
      const template = { ...templates[0], owner, user_can_change }
      component.templates.set([template])
      fixture.detectChanges()
      await fixture.whenStable()

      expect(fixture.nativeElement.querySelector('.text-start').disabled).toBe(
        !editable
      )
      expect(
        fixture.nativeElement.querySelector('.form-switch input').disabled
      ).toBe(!editable)
      const buttons = Array.from<HTMLButtonElement>(
        fixture.nativeElement.querySelectorAll('button')
      )
      for (const button of buttons.filter(
        (button) => button.textContent.trim() === 'Edit'
      )) {
        expect(button.disabled).toBe(!editable)
      }
      for (const button of buttons.filter(
        (button) => button.textContent.trim() === 'Delete'
      )) {
        expect(button.disabled).toBe(!deletable)
      }
    }
  )

  it('should allow a superuser to manage another users template', () => {
    TestBed.inject(PermissionsService).initialize([], {
      id: 1,
      is_superuser: true,
    } as User)
    component.templates.set([
      { ...templates[0], owner: 2, user_can_change: false },
    ])
    fixture.detectChanges()
    expect(fixture.nativeElement.querySelector('.text-start').disabled).toBe(
      false
    )
    expect(
      fixture.nativeElement.querySelector('.btn-outline-danger').disabled
    ).toBe(false)
  })

  it('should not open mutation dialogs or patch a view-only template', () => {
    const template = { ...templates[0], owner: 2, user_can_change: false }
    const open = jest.spyOn(modalService, 'open')
    const patch = jest.spyOn(ocrTemplateService, 'patch')
    component.editTemplate(template)
    component.toggleTemplateEnabled(template)
    component.deleteTemplate(template)
    expect(open).not.toHaveBeenCalled()
    expect(patch).not.toHaveBeenCalled()
  })

  it('should require global edit permission even for an owned template', () => {
    TestBed.inject(PermissionsService).initialize(['view_ocrtemplate'], {
      id: 1,
    } as User)
    fixture.destroy()
    fixture = TestBed.createComponent(OcrTemplatesComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
    expect(fixture.nativeElement.querySelector('.text-start').disabled).toBe(
      true
    )
    expect(fixture.nativeElement.querySelector('.form-switch input')).toBeNull()
  })

  it('should support create, show notification on error / success', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastSuccessSpy = jest.spyOn(toastService, 'showSuccess')
    const reloadSpy = jest.spyOn(component, 'reload')

    fixture.debugElement
      .queryAll(By.css('pngx-page-header button'))
      .find((button) => button.nativeElement.textContent.includes('Add'))
      .triggerEventHandler('click')

    const editor = modal.componentInstance as OcrTemplateEditorComponent
    expect(editor).toBeInstanceOf(OcrTemplateEditorComponent)
    expect(editor.object).toBeUndefined()

    editor.failed.emit({ error: 'error creating template' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    editor.succeeded.emit(templates[0])
    expect(toastSuccessSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should pass the template to the editor', () => {
    component.editTemplate(templates[0])
    expect(modal.componentInstance.object).toBe(templates[0])
  })

  it('should confirm closing the editor with unsaved changes', async () => {
    const confirmSpy = jest
      .spyOn(TestBed.inject(DirtyFormGuard), 'confirmChanges')
      .mockReturnValue(of(false))
    component.editTemplate()
    const editor = modal.componentInstance as OcrTemplateEditorComponent
    editor.ngOnInit()

    modal.dismiss()
    await fixture.whenStable()
    expect(confirmSpy).not.toHaveBeenCalled()

    component.editTemplate()
    const dirtyEditor = modal.componentInstance as OcrTemplateEditorComponent
    dirtyEditor.ngOnInit()
    dirtyEditor.template.name = 'Changed'
    modal.dismiss()
    await fixture.whenStable()
    expect(confirmSpy).toHaveBeenCalled()
    expect(modalService.hasOpenModals()).toBe(true)

    dirtyEditor.saving.set(true)
    confirmSpy.mockClear()
    modal.dismiss()
    await fixture.whenStable()
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(modalService.hasOpenModals()).toBe(true)
  })

  it('should only send the enabled flag when toggling', () => {
    const patchSpy = jest
      .spyOn(ocrTemplateService, 'patch')
      .mockReturnValueOnce(throwError(() => new Error('error toggling')))
      .mockReturnValueOnce(of(templates[0]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastSuccessSpy = jest.spyOn(toastService, 'showSuccess')
    const reloadSpy = jest.spyOn(component, 'reload')

    const toggle = fixture.debugElement.query(By.css('.form-switch input'))
    toggle.nativeElement.click()
    expect(patchSpy).toHaveBeenCalledWith({ id: 1, enabled: false })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalledTimes(1)

    component.toggleTemplateEnabled(templates[0])
    expect(toastSuccessSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalledTimes(2)
  })

  it('should support delete, show notification on error / success', () => {
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastSuccessSpy = jest.spyOn(toastService, 'showSuccess')
    const deleteSpy = jest.spyOn(ocrTemplateService, 'delete')
    const reloadSpy = jest.spyOn(component, 'reload')

    component.deleteTemplate(templates[0])
    const dialog = modal.componentInstance as ConfirmDialogComponent

    deleteSpy.mockReturnValueOnce(throwError(() => new Error('error deleting')))
    dialog.confirmClicked.emit()
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(dialog.buttonsEnabled()).toBe(true)
    expect(reloadSpy).not.toHaveBeenCalled()

    deleteSpy.mockReturnValueOnce(of(true))
    dialog.confirmClicked.emit()
    expect(toastSuccessSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
  })
})
