import { ComponentFixture, TestBed } from '@angular/core/testing'

import { CustomFieldsDropdownComponent } from './custom-fields-dropdown.component'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { ToastService } from 'src/app/services/toast.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { of } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { SelectComponent } from '../input/select/select.component'
import { NgSelectModule } from '@ng-select/ng-select'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbDropdownModule,
  NgbModal,
  NgbModalModule,
  NgbModalRef,
} from '@ng-bootstrap/ng-bootstrap'
import { CustomFieldEditDialogComponent } from '../edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { By } from '@angular/platform-browser'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'

const fields: CustomField[] = [
  {
    id: 0,
    name: 'Field 1',
    data_type: CustomFieldDataType.Integer,
  },
  {
    id: 1,
    name: 'Field 2',
    data_type: CustomFieldDataType.String,
  },
]

describe('CustomFieldsDropdownComponent', () => {
  let component: CustomFieldsDropdownComponent
  let fixture: ComponentFixture<CustomFieldsDropdownComponent>
  let customFieldService: CustomFieldsService
  let toastService: ToastService
  let modalService: NgbModal

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [CustomFieldsDropdownComponent, SelectComponent],
      imports: [
        HttpClientTestingModule,
        NgSelectModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModalModule,
        NgbDropdownModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    })
    customFieldService = TestBed.inject(CustomFieldsService)
    toastService = TestBed.inject(ToastService)
    modalService = TestBed.inject(NgbModal)
    jest.spyOn(customFieldService, 'listAll').mockReturnValue(
      of({
        all: fields.map((f) => f.id),
        count: fields.length,
        results: fields.concat([]),
      })
    )
    fixture = TestBed.createComponent(CustomFieldsDropdownComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should support add field', () => {
    let addedField
    component.added.subscribe((f) => (addedField = f))
    component.documentId = 11
    component.field = fields[0].id
    component.addField()
    expect(addedField).not.toBeUndefined()
  })

  it('should clear field on open / close, updated unused fields', () => {
    component.field = fields[1].id
    component.onOpenClose()
    expect(component.field).toBeUndefined()

    expect(component.unusedFields).toEqual(fields)
    const updateSpy = jest.spyOn(
      CustomFieldsDropdownComponent.prototype as any,
      'updateUnusedFields'
    )
    component.existingFields = [{ field: fields[1].id } as any]
    component.onOpenClose()
    expect(updateSpy).toHaveBeenCalled()
    expect(component.unusedFields).toEqual([fields[0]])
  })

  it('should support creating field, show error if necessary', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const getFieldsSpy = jest.spyOn(
      CustomFieldsDropdownComponent.prototype as any,
      'getFields'
    )

    const createButton = fixture.debugElement.queryAll(By.css('button'))[1]
    createButton.triggerEventHandler('click')

    expect(modal).not.toBeUndefined()
    const editDialog = modal.componentInstance as CustomFieldEditDialogComponent

    // fail first
    editDialog.failed.emit({ error: 'error creating field' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(getFieldsSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(fields[0])
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(getFieldsSpy).toHaveBeenCalled()
  })

  it('should support creating field with name', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    component.createField('Foo bar')

    expect(modal).not.toBeUndefined()
    const editDialog = modal.componentInstance as CustomFieldEditDialogComponent
    expect(editDialog.object.name).toEqual('Foo bar')
  })
})
