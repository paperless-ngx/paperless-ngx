import {
  ComponentFixture,
  fakeAsync,
  TestBed,
  tick,
} from '@angular/core/testing'
import {
  CustomFieldQueriesModel,
  CustomFieldsQueryDropdownComponent,
} from './custom-fields-query-dropdown.component'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { of } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import {
  CUSTOM_FIELD_QUERY_OPERATORS_BY_GROUP,
  CustomFieldQueryLogicalOperator,
  CustomFieldQueryOperatorGroups,
} from 'src/app/data/custom-field-query'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import {
  CustomFieldQueryExpression,
  CustomFieldQueryAtom,
  CustomFieldQueryElement,
} from 'src/app/utils/custom-field-query-element'
import { NgSelectModule } from '@ng-select/ng-select'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'

const customFields = [
  {
    id: 1,
    name: 'Test Field',
    data_type: CustomFieldDataType.String,
    extra_data: {},
  },
  {
    id: 2,
    name: 'Test Select Field',
    data_type: CustomFieldDataType.Select,
    extra_data: { select_options: ['Option 1', 'Option 2'] },
  },
]

describe('CustomFieldsQueryDropdownComponent', () => {
  let component: CustomFieldsQueryDropdownComponent
  let fixture: ComponentFixture<CustomFieldsQueryDropdownComponent>
  let customFieldsService: CustomFieldsService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [CustomFieldsQueryDropdownComponent],
      imports: [
        NgbDropdownModule,
        NgxBootstrapIconsModule.pick(allIcons),
        NgSelectModule,
        FormsModule,
        ReactiveFormsModule,
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    customFieldsService = TestBed.inject(CustomFieldsService)
    jest.spyOn(customFieldsService, 'listAll').mockReturnValue(
      of({
        count: customFields.length,
        all: customFields.map((f) => f.id),
        results: customFields,
      })
    )
    fixture = TestBed.createComponent(CustomFieldsQueryDropdownComponent)
    component = fixture.componentInstance
    component.icon = 'ui-radios'
    fixture.detectChanges()
  })

  it('should initialize custom fields on creation', () => {
    expect(component.customFields).toEqual(customFields)
  })

  it('should add an expression when opened if queries are empty', () => {
    component.selectionModel.clear()
    component.onOpenChange(true)
    expect(component.selectionModel.queries.length).toBe(1)
  })

  it('should support reset the selection model', () => {
    component.selectionModel.addExpression()
    component.reset()
    expect(component.selectionModel.isEmpty()).toBeTruthy()
  })

  it('should get operators for a field', () => {
    const field: CustomField = {
      id: 1,
      name: 'Test Field',
      data_type: CustomFieldDataType.String,
      extra_data: {},
    }
    component.customFields = [field]
    const operators = component.getOperatorsForField(1)
    expect(operators.length).toEqual(
      [
        ...CUSTOM_FIELD_QUERY_OPERATORS_BY_GROUP[
          CustomFieldQueryOperatorGroups.Basic
        ],
        ...CUSTOM_FIELD_QUERY_OPERATORS_BY_GROUP[
          CustomFieldQueryOperatorGroups.String
        ],
      ].length
    )

    // Fallback to basic operators if field is not found
    const operators2 = component.getOperatorsForField(2)
    expect(operators2.length).toEqual(
      CUSTOM_FIELD_QUERY_OPERATORS_BY_GROUP[
        CustomFieldQueryOperatorGroups.Basic
      ].length
    )
  })

  it('should get select options for a field', () => {
    const field: CustomField = {
      id: 1,
      name: 'Test Field',
      data_type: CustomFieldDataType.Select,
      extra_data: { select_options: ['Option 1', 'Option 2'] },
    }
    component.customFields = [field]
    const options = component.getSelectOptionsForField(1)
    expect(options).toEqual(['Option 1', 'Option 2'])

    // Fallback to empty array if field is not found
    const options2 = component.getSelectOptionsForField(2)
    expect(options2).toEqual([])
  })

  it('should remove an element from the selection model', () => {
    const expression = new CustomFieldQueryExpression()
    const atom = new CustomFieldQueryAtom()
    ;(expression.value as CustomFieldQueryElement[]).push(atom)
    component.selectionModel.addExpression(expression)
    component.removeElement(atom)
    expect(component.selectionModel.isEmpty()).toBeTruthy()
    const expression2 = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.And,
      [
        [1, 'icontains', 'test'],
        [2, 'icontains', 'test'],
      ],
    ])
    component.selectionModel.addExpression(expression2)
    component.removeElement(expression2)
    expect(component.selectionModel.isEmpty()).toBeTruthy()
  })

  it('should emit selectionModelChange when model changes', () => {
    const nextSpy = jest.spyOn(component.selectionModelChange, 'next')
    const atom = new CustomFieldQueryAtom([1, 'icontains', 'test'])
    component.selectionModel.addAtom(atom)
    atom.changed.next(atom)
    expect(nextSpy).toHaveBeenCalled()
  })

  it('should complete selection model subscription when new selection model is set', () => {
    const completeSpy = jest.spyOn(component.selectionModel.changed, 'complete')
    const selectionModel = new CustomFieldQueriesModel()
    component.selectionModel = selectionModel
    expect(completeSpy).toHaveBeenCalled()
  })

  it('should support adding an atom', () => {
    const expression = new CustomFieldQueryExpression()
    component.addAtom(expression)
    expect(expression.value.length).toBe(1)
  })

  it('should support adding an expression', () => {
    const expression = new CustomFieldQueryExpression()
    component.addExpression(expression)
    expect(expression.value.length).toBe(1)
  })

  it('should support getting a custom field by ID', () => {
    expect(component.getCustomFieldByID(1)).toEqual(customFields[0])
  })

  it('should sanitize name from title', () => {
    component.title = 'Test Title'
    expect(component.name).toBe('test_title')
  })

  it('should add a default atom on open and focus the select field', fakeAsync(() => {
    expect(component.selectionModel.queries.length).toBe(0)
    component.onOpenChange(true)
    fixture.detectChanges()
    tick()
    expect(component.selectionModel.queries.length).toBe(1)
    expect(window.document.activeElement.tagName).toBe('INPUT')
  }))

  describe('CustomFieldQueriesModel', () => {
    let model: CustomFieldQueriesModel

    beforeEach(() => {
      model = new CustomFieldQueriesModel()
    })

    it('should initialize with empty queries', () => {
      expect(model.queries).toEqual([])
    })

    it('should clear queries and fire event', () => {
      const nextSpy = jest.spyOn(model.changed, 'next')
      model.addExpression()
      model.clear()
      expect(model.queries).toEqual([])
      expect(nextSpy).toHaveBeenCalledWith(model)
    })

    it('should clear queries without firing event', () => {
      const nextSpy = jest.spyOn(model.changed, 'next')
      model.addExpression()
      model.clear(false)
      expect(model.queries).toEqual([])
      expect(nextSpy).not.toHaveBeenCalled()
    })

    it('should validate an empty model as invalid', () => {
      expect(model.isValid()).toBeFalsy()
    })

    it('should validate a model with valid expression as valid', () => {
      const expression = new CustomFieldQueryExpression()
      const atom = new CustomFieldQueryAtom([1, 'icontains', 'test'])
      const atom2 = new CustomFieldQueryAtom([2, 'icontains', 'test'])
      const expression2 = new CustomFieldQueryExpression()
      expression2.addAtom(atom)
      expression2.addAtom(atom2)
      expression.addExpression(expression2)
      model.addExpression(expression)
      expect(model.isValid()).toBeTruthy()
    })

    it('should validate a model with invalid expression as invalid', () => {
      const expression = new CustomFieldQueryExpression()
      model.addExpression(expression)
      expect(model.isValid()).toBeFalsy()
    })

    it('should validate an atom with in or contains operator', () => {
      const atom = new CustomFieldQueryAtom([1, 'in', '[1,2,3]'])
      expect(model['validateAtom'].apply(null, [atom])).toBeTruthy()
      atom.operator = 'contains'
      atom.value = [1, 2, 3]
      expect(model['validateAtom'].apply(null, [atom])).toBeTruthy()
      atom.value = null
      expect(model['validateAtom'].apply(null, [atom])).toBeFalsy()
    })

    it('should check if model is empty', () => {
      expect(model.isEmpty()).toBeTruthy()
      model.addExpression()
      expect(model.isEmpty()).toBeTruthy()
      const atom = new CustomFieldQueryAtom([1, 'icontains', 'test'])
      model.addAtom(atom)
      expect(model.isEmpty()).toBeFalsy()
    })

    it('should add an atom to the model', () => {
      const atom = new CustomFieldQueryAtom([1, 'icontains', 'test'])
      model.addAtom(atom)
      expect(model.queries.length).toBe(1)
      expect(
        (model.queries[0] as CustomFieldQueryExpression).value.length
      ).toBe(1)
    })

    it('should add an expression to the model, propagate changes', () => {
      const expression = new CustomFieldQueryExpression()
      model.addExpression(expression)
      expect(model.queries.length).toBe(1)
      const expression2 = new CustomFieldQueryExpression([
        CustomFieldQueryLogicalOperator.And,
        [
          [1, 'icontains', 'test'],
          [2, 'icontains', 'test'],
        ],
      ])
      model.addExpression(expression2)
      const nextSpy = jest.spyOn(model.changed, 'next')
      expression2.changed.next(expression2)
      expect(nextSpy).toHaveBeenCalled()
    })

    it('should remove an element from the model', () => {
      const expression = new CustomFieldQueryExpression([
        CustomFieldQueryLogicalOperator.And,
        [
          [1, 'icontains', 'test'],
          [2, 'icontains', 'test'],
        ],
      ])
      const atom = new CustomFieldQueryAtom([1, 'icontains', 'test'])
      const expression2 = new CustomFieldQueryExpression([
        CustomFieldQueryLogicalOperator.And,
        [
          [3, 'icontains', 'test'],
          [4, 'icontains', 'test'],
        ],
      ])
      expression.addAtom(atom)
      expression2.addExpression(expression)
      model.addExpression(expression2)
      model.removeElement(atom)
      expect(model.queries.length).toBe(1)
      model.removeElement(expression2)
    })

    it('should fire changed event when an atom changes', () => {
      const nextSpy = jest.spyOn(model.changed, 'next')
      const atom = new CustomFieldQueryAtom([1, 'icontains', 'test'])
      model.addAtom(atom)
      atom.changed.next(atom)
      expect(nextSpy).toHaveBeenCalledWith(model)
    })

    it('should complete changed subject when element is removed', () => {
      const expression = new CustomFieldQueryExpression()
      const atom = new CustomFieldQueryAtom([1, 'icontains', 'test'])
      ;(expression.value as CustomFieldQueryElement[]).push(atom)
      model.addExpression(expression)
      const completeSpy = jest.spyOn(atom.changed, 'complete')
      model.removeElement(atom)
      expect(completeSpy).toHaveBeenCalled()
    })
  })
})
