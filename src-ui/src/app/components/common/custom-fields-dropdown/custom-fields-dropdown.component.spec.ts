import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import {
  NgbDropdownModule,
  NgbModal,
  NgbModalModule,
  NgbModalRef,
} from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { ToastService } from 'src/app/services/toast.service'
import { CustomFieldEditDialogComponent } from '../edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { SelectComponent } from '../input/select/select.component'
import { CustomFieldsDropdownComponent } from './custom-fields-dropdown.component'

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
        NgSelectModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModalModule,
        NgbDropdownModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
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
    component.addField({ field: fields[0].id } as any)
    expect(addedField).not.toBeUndefined()
  })

  it('should support filtering fields', () => {
    const input = fixture.debugElement.query(By.css('input'))
    input.nativeElement.value = 'Field 1'
    input.triggerEventHandler('input', { target: input.nativeElement })
    fixture.detectChanges()
    expect(component.filteredFields.length).toEqual(1)
    expect(component.filteredFields[0].name).toEqual('Field 1')
  })

  it('should support update unused fields', () => {
    component.existingFields = [{ field: fields[0].id } as any]
    component['updateUnusedFields']()
    expect(component['unusedFields'].length).toEqual(1)
    expect(component['unusedFields'][0].name).toEqual('Field 2')
  })

  it('should support getting data type label', () => {
    expect(component.getDataTypeLabel(CustomFieldDataType.Integer)).toEqual(
      'Integer'
    )
  })

  it('should support creating field, show error if necessary, then add', fakeAsync(() => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const getFieldsSpy = jest.spyOn(
      CustomFieldsDropdownComponent.prototype as any,
      'getFields'
    )
    const addFieldSpy = jest.spyOn(component, 'addField')

    const createButton = fixture.debugElement.queryAll(By.css('button'))[3]
    createButton.triggerEventHandler('click')

    expect(modal).not.toBeUndefined()
    const editDialog = modal.componentInstance as CustomFieldEditDialogComponent

    // fail first
    editDialog.failed.emit({ error: 'error creating field' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(getFieldsSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(fields[0])
    tick(100)
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(getFieldsSpy).toHaveBeenCalled()
    expect(addFieldSpy).toHaveBeenCalled()
  }))

  it('should support creating field with name', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    component.createField('Foo bar')

    expect(modal).not.toBeUndefined()
    const editDialog = modal.componentInstance as CustomFieldEditDialogComponent
    expect(editDialog.object.name).toEqual('Foo bar')
  })

  it('should support arrow keyboard navigation', fakeAsync(() => {
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)
    const filterInputEl: HTMLInputElement =
      component.listFilterTextInput.nativeElement
    expect(document.activeElement).toEqual(filterInputEl)
    const itemButtons = Array.from(
      (fixture.nativeElement as HTMLDivElement).querySelectorAll(
        '.custom-fields-dropdown button'
      )
    ).filter((b) => b.textContent.includes('Field'))
    filterInputEl.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    )
    expect(document.activeElement).toEqual(itemButtons[0])
    itemButtons[0].dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    )
    expect(document.activeElement).toEqual(itemButtons[1])
    itemButtons[1].dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true })
    )
    expect(document.activeElement).toEqual(itemButtons[0])
    itemButtons[0].dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true })
    )
    expect(document.activeElement).toEqual(filterInputEl)
    filterInputEl.value = 'foo'
    component.filterText = 'foo'

    // dont move focus if we're traversing the field
    filterInputEl.selectionStart = 1
    expect(document.activeElement).toEqual(filterInputEl)

    // now we're at end, so move focus
    filterInputEl.selectionStart = 3
    filterInputEl.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    )
    expect(document.activeElement).toEqual(itemButtons[0])
  }))

  it('should support arrow keyboard navigation after tab keyboard navigation', fakeAsync(() => {
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)
    const filterInputEl: HTMLInputElement =
      component.listFilterTextInput.nativeElement
    expect(document.activeElement).toEqual(filterInputEl)
    const itemButtons = Array.from(
      (fixture.nativeElement as HTMLDivElement).querySelectorAll(
        '.custom-fields-dropdown button'
      )
    ).filter((b) => b.textContent.includes('Field'))
    filterInputEl.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', bubbles: true })
    )
    itemButtons[0]['focus']() // normally handled by browser
    itemButtons[0].dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', bubbles: true })
    )
    itemButtons[1]['focus']() // normally handled by browser
    itemButtons[1].dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'Tab',
        shiftKey: true,
        bubbles: true,
      })
    )
    itemButtons[0]['focus']() // normally handled by browser
    itemButtons[0].dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    )
    expect(document.activeElement).toEqual(itemButtons[1])
  }))

  it('should support enter keyboard navigation', fakeAsync(() => {
    jest.spyOn(component, 'canCreateFields', 'get').mockReturnValue(true)
    const addFieldSpy = jest.spyOn(component, 'addField')
    const createFieldSpy = jest.spyOn(component, 'createField')
    component.filterText = 'Field 1'
    component.listFilterEnter()
    expect(addFieldSpy).toHaveBeenCalled()

    component.filterText = 'Field 3'
    component.listFilterEnter()
    expect(createFieldSpy).toHaveBeenCalledWith('Field 3')

    addFieldSpy.mockClear()
    createFieldSpy.mockClear()

    component.filterText = undefined
    component.listFilterEnter()
    expect(createFieldSpy).not.toHaveBeenCalled()
    expect(addFieldSpy).not.toHaveBeenCalled()
  }))
})
