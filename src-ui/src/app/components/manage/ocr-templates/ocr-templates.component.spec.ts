import { EventEmitter, signal, WritableSignal } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbModal, NgbModalOptions } from '@ng-bootstrap/ng-bootstrap'
import { of, Subject } from 'rxjs'
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
    saving: false,
    isDirty: false,
    succeeded: new EventEmitter<OcrTemplate>(),
  }
  const modal = { open: jest.fn() }
  const dirtyFormGuard = { confirmChanges: jest.fn() }
  const templates = { delete: jest.fn() }
  const toast = { showError: jest.fn() }

  beforeEach(async () => {
    editor.object = undefined
    editor.saving = false
    editor.isDirty = false
    editor.succeeded = new EventEmitter<OcrTemplate>()
    modal.open.mockReset().mockImplementation((_, modalOptions) => {
      options = modalOptions
      return { componentInstance: editor }
    })
    dirtyFormGuard.confirmChanges.mockReset().mockReturnValue(of(true))
    templates.delete.mockReset()
    toast.showError.mockReset()
    await TestBed.configureTestingModule({
      imports: [OcrTemplatesComponent],
      providers: [
        { provide: NgbModal, useValue: modal },
        { provide: DirtyFormGuard, useValue: dirtyFormGuard },
        { provide: PermissionsService, useValue: {} },
        { provide: OcrTemplateService, useValue: templates },
        { provide: DocumentTypeService, useValue: {} },
        { provide: ToastService, useValue: toast },
      ],
    })
      .overrideComponent(OcrTemplatesComponent, {
        set: { template: '', imports: [] },
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

    editor.saving = true
    expect(options.beforeDismiss()).toBe(false)
    expect(dirtyFormGuard.confirmChanges).toHaveBeenCalledTimes(2)
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
