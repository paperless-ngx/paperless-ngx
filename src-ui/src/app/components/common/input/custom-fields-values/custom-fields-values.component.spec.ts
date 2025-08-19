import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { of } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { CustomFieldsValuesComponent } from './custom-fields-values.component'

describe('CustomFieldsValuesComponent', () => {
  let component: CustomFieldsValuesComponent
  let fixture: ComponentFixture<CustomFieldsValuesComponent>
  let customFieldsService: CustomFieldsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [FormsModule, ReactiveFormsModule, CustomFieldsValuesComponent],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(CustomFieldsValuesComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    customFieldsService = TestBed.inject(CustomFieldsService)
    jest.spyOn(customFieldsService, 'listAll').mockReturnValue(
      of({
        all: [1],
        count: 1,
        results: [
          {
            id: 1,
            name: 'Field 1',
            data_type: CustomFieldDataType.String,
          } as CustomField,
        ],
      })
    )
    fixture.detectChanges()
  })

  beforeEach(() => {
    fixture = TestBed.createComponent(CustomFieldsValuesComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should set selectedFields and map values correctly', () => {
    component.value = { 1: 'value1' }
    component.selectedFields = [1, 2]
    expect(component.selectedFields).toEqual([1, 2])
    expect(component.value).toEqual({ 1: 'value1', 2: null })
  })

  it('should return the correct custom field by id', () => {
    const field = component.getCustomField(1)
    expect(field).toEqual({
      id: 1,
      name: 'Field 1',
      data_type: CustomFieldDataType.String,
    } as CustomField)
  })
})
