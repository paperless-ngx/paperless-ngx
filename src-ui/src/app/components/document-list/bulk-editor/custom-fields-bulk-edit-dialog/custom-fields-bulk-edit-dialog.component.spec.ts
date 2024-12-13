import { ComponentFixture, TestBed } from '@angular/core/testing'

import { provideHttpClient } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { of, throwError } from 'rxjs'
import { SelectComponent } from 'src/app/components/common/input/select/select.component'
import { CustomFieldDataType } from 'src/app/data/custom-field'
import { DocumentService } from 'src/app/services/rest/document.service'
import { CustomFieldsBulkEditDialogComponent } from './custom-fields-bulk-edit-dialog.component'

describe('CustomFieldsBulkEditDialogComponent', () => {
  let component: CustomFieldsBulkEditDialogComponent
  let fixture: ComponentFixture<CustomFieldsBulkEditDialogComponent>
  let documentService: DocumentService
  let activeModal: NgbActiveModal

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [CustomFieldsBulkEditDialogComponent, SelectComponent],
      imports: [FormsModule, ReactiveFormsModule, NgbModule, NgSelectModule],
      providers: [
        NgbActiveModal,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(CustomFieldsBulkEditDialogComponent)
    component = fixture.componentInstance
    documentService = TestBed.inject(DocumentService)
    activeModal = TestBed.inject(NgbActiveModal)
    fixture.detectChanges()
  })

  it('should initialize form controls based on selected field ids', () => {
    component.customFields = [
      { id: 1, name: 'Field 1', data_type: CustomFieldDataType.String },
      { id: 2, name: 'Field 2', data_type: CustomFieldDataType.Integer },
    ]
    component.fieldsToAddIds = [1, 2]
    expect(component.form.contains('1')).toBeTruthy()
    expect(component.form.contains('2')).toBeTruthy()
  })

  it('should emit succeeded event and close modal on successful save', () => {
    const editSpy = jest
      .spyOn(documentService, 'bulkEdit')
      .mockReturnValue(of('Success'))
    const successSpy = jest.spyOn(component.succeeded, 'emit')

    component.documents = [1, 2]
    component.fieldsToAddIds = [1]
    component.form.controls['1'].setValue('Value 1')
    component.save()

    expect(editSpy).toHaveBeenCalled()
    expect(successSpy).toHaveBeenCalled()
  })

  it('should emit failed event on save error', () => {
    const editSpy = jest
      .spyOn(documentService, 'bulkEdit')
      .mockReturnValue(throwError(new Error('Error')))
    const failSpy = jest.spyOn(component.failed, 'emit')

    component.documents = [1, 2]
    component.fieldsToAddIds = [1]
    component.form.controls['1'].setValue('Value 1')
    component.save()

    expect(editSpy).toHaveBeenCalled()
    expect(failSpy).toHaveBeenCalled()
  })

  it('should close modal on cancel', () => {
    const activeModalSpy = jest.spyOn(activeModal, 'close')
    component.cancel()
    expect(activeModalSpy).toHaveBeenCalled()
  })

  it('should remove field from selected fields', () => {
    component.fieldsToAddIds = [1, 2]
    component.removeField(1)
    expect(component.fieldsToAddIds).toEqual([2])
  })
})
