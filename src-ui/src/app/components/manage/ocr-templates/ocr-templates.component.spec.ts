import { EventEmitter } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbModal, NgbModalOptions } from '@ng-bootstrap/ng-bootstrap'
import { of } from 'rxjs'
import { OcrTemplate } from 'src/app/data/ocr-template'
import { DirtyFormGuard } from 'src/app/guards/dirty-form.guard'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { ToastService } from 'src/app/services/toast.service'
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
    await TestBed.configureTestingModule({
      imports: [OcrTemplatesComponent],
      providers: [
        { provide: NgbModal, useValue: modal },
        { provide: DirtyFormGuard, useValue: dirtyFormGuard },
        { provide: PermissionsService, useValue: {} },
        { provide: OcrTemplateService, useValue: {} },
        { provide: DocumentTypeService, useValue: {} },
        { provide: ToastService, useValue: {} },
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
})
