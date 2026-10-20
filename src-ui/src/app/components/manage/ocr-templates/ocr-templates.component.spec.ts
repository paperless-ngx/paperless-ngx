import { EventEmitter, signal, WritableSignal } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbModal, NgbModalOptions } from '@ng-bootstrap/ng-bootstrap'
import { of, Subject } from 'rxjs'
import { DocumentType } from 'src/app/data/document-type'
import { OcrTemplate } from 'src/app/data/ocr-template'
import { DirtyFormGuard } from 'src/app/guards/dirty-form.guard'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { OcrTemplateEditorComponent } from './ocr-template-editor/ocr-template-editor.component'
import { OcrTemplatesComponent } from './ocr-templates.component'

describe('OcrTemplatesComponent', () => {
  let fixture: ComponentFixture<OcrTemplatesComponent>
  let component: OcrTemplatesComponent
  let options: NgbModalOptions
  const editor = {
    object: undefined as OcrTemplate,
    saving: signal(false),
    isDirty: false,
    succeeded: new EventEmitter<OcrTemplate>(),
  }
  const modal = { open: jest.fn() }
  const dirtyFormGuard = { confirmChanges: jest.fn() }
  const templates = { delete: jest.fn(), patch: jest.fn(), listAll: jest.fn() }
  const documentTypes = { listAll: jest.fn() }
  const toast = { showError: jest.fn() }

  beforeEach(async () => {
    editor.object = undefined
    editor.saving.set(false)
    editor.isDirty = false
    editor.succeeded = new EventEmitter<OcrTemplate>()
    modal.open.mockReset().mockImplementation((_, modalOptions) => {
      options = modalOptions
      return { componentInstance: editor }
    })
    dirtyFormGuard.confirmChanges.mockReset().mockReturnValue(of(true))
    templates.delete.mockReset()
    templates.patch.mockReset()
    templates.listAll.mockReset().mockReturnValue(of({ results: [] }))
    documentTypes.listAll.mockReset().mockReturnValue(of({ results: [] }))
    toast.showError.mockReset()
    await TestBed.configureTestingModule({
      imports: [OcrTemplatesComponent],
      providers: [
        { provide: NgbModal, useValue: modal },
        { provide: DirtyFormGuard, useValue: dirtyFormGuard },
        { provide: PermissionsService, useValue: {} },
        { provide: OcrTemplateService, useValue: templates },
        { provide: DocumentTypeService, useValue: documentTypes },
        { provide: ToastService, useValue: toast },
      ],
    })
      .overrideComponent(OcrTemplatesComponent, {
        set: {
          template: `
            @for (template of templates(); track template.id) {
              <span class="name">{{ template.name }}</span>
              <span class="document-type">{{ getDocumentTypeName(template) }}</span>
              <input type="checkbox" [checked]="template.enabled" />
            }
          `,
          imports: [],
        },
      })
      .compileComponents()
    fixture = TestBed.createComponent(OcrTemplatesComponent)
    component = fixture.componentInstance
  })

  it('opens creation in a dialog and refreshes the list after saving', () => {
    const reload = jest.spyOn(component, 'reload').mockImplementation(() => {})
    component.createTemplate()

    expect(modal.open).toHaveBeenCalledWith(
      OcrTemplateEditorComponent,
      expect.any(Object)
    )
    expect(editor.object).toBeUndefined()
    expect(options.backdrop).toBe('static')
    expect(options.beforeDismiss()).toBe(true)
    editor.succeeded.emit({ id: 3 } as OcrTemplate)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('passes the selected template to the same editor dialog', () => {
    const template = { id: 3, name: 'Invoices' } as OcrTemplate
    component.editTemplate(template)

    expect(editor.object).toBe(template)
  })

  it('confirms dismissal only when dirty and never dismisses while saving', async () => {
    component.createTemplate()
    editor.isDirty = true
    dirtyFormGuard.confirmChanges.mockReturnValue(of(false))
    expect(await options.beforeDismiss()).toBe(false)
    dirtyFormGuard.confirmChanges.mockReturnValue(of(true))
    expect(await options.beforeDismiss()).toBe(true)
    expect(dirtyFormGuard.confirmChanges).toHaveBeenCalledTimes(2)

    editor.saving.set(true)
    expect(options.beforeDismiss()).toBe(false)
    expect(dirtyFormGuard.confirmChanges).toHaveBeenCalledTimes(2)
  })

  it('renders asynchronously loaded templates and type names without manual change detection', async () => {
    const pendingTemplates = new Subject<{ results: OcrTemplate[] }>()
    const pendingTypes = new Subject<{ results: DocumentType[] }>()
    templates.listAll.mockReturnValue(pendingTemplates)
    documentTypes.listAll.mockReturnValue(pendingTypes)
    fixture.detectChanges()

    pendingTemplates.next({
      results: [{ id: 3, name: 'Invoices', document_type: 2 } as OcrTemplate],
    })
    await fixture.whenStable()
    expect(fixture.nativeElement.querySelector('.name').textContent).toBe(
      'Invoices'
    )

    pendingTypes.next({ results: [{ id: 2, name: 'Invoice' } as DocumentType] })
    await fixture.whenStable()
    expect(
      fixture.nativeElement.querySelector('.document-type').textContent
    ).toBe('Invoice')
  })

  it('renders toggle rollback after an asynchronous failure without manual change detection', async () => {
    const template = { id: 3, name: 'Invoices', enabled: true } as OcrTemplate
    templates.listAll.mockReturnValue(of({ results: [template] }))
    const pending = new Subject<OcrTemplate>()
    templates.patch.mockReturnValue(pending)
    fixture.detectChanges()

    component.toggleTemplate(template, false)
    await fixture.whenStable()
    expect(fixture.nativeElement.querySelector('input').checked).toBe(false)
    expect(templates.patch).toHaveBeenCalledWith({
      ...template,
      enabled: false,
    })
    expect(template.enabled).toBe(true)

    const error = new Error('Update failed')
    pending.error(error)
    await fixture.whenStable()

    expect(fixture.nativeElement.querySelector('input').checked).toBe(true)
    expect(toast.showError).toHaveBeenCalledWith(expect.any(String), error)
  })

  describe('deletion', () => {
    const template = { id: 3, name: 'Invoices' } as OcrTemplate
    let dialog: {
      confirmClicked: EventEmitter<void>
      buttonsEnabled: WritableSignal<boolean>
      messageBold?: string
    }
    let close: jest.Mock
    let reload: jest.SpyInstance

    beforeEach(() => {
      dialog = {
        confirmClicked: new EventEmitter<void>(),
        buttonsEnabled: signal(true),
      }
      close = jest.fn()
      modal.open.mockReturnValue({ componentInstance: dialog, close })
      reload = jest.spyOn(component, 'reload').mockImplementation(() => {})
    })

    it('keeps the confirmation open and disables buttons until deletion succeeds', () => {
      const pending = new Subject<void>()
      templates.delete.mockReturnValue(pending)
      component.deleteTemplate(template)

      expect(modal.open).toHaveBeenCalledWith(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      expect(dialog.messageBold).toBe(template.name)
      expect(templates.delete).not.toHaveBeenCalled()
      dialog.confirmClicked.emit()

      expect(templates.delete).toHaveBeenCalledWith(template)
      expect(dialog.buttonsEnabled()).toBe(false)
      expect(close).not.toHaveBeenCalled()
      expect(reload).not.toHaveBeenCalled()

      pending.next()
      pending.complete()

      expect(close).toHaveBeenCalledTimes(1)
      expect(reload).toHaveBeenCalledTimes(1)
    })

    it('shows errors and allows retrying without closing the confirmation', () => {
      const pending = new Subject<void>()
      templates.delete
        .mockReturnValueOnce(pending)
        .mockReturnValue(of(undefined))
      component.deleteTemplate(template)
      dialog.confirmClicked.emit()
      const error = new Error('Delete failed')
      pending.error(error)

      expect(toast.showError).toHaveBeenCalledWith(expect.any(String), error)
      expect(dialog.buttonsEnabled()).toBe(true)
      expect(close).not.toHaveBeenCalled()
      expect(reload).not.toHaveBeenCalled()

      dialog.confirmClicked.emit()

      expect(templates.delete).toHaveBeenCalledTimes(2)
      expect(close).toHaveBeenCalledTimes(1)
      expect(reload).toHaveBeenCalledTimes(1)
    })
  })
})
