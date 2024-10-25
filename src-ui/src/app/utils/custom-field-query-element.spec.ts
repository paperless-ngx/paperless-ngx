import {
  CustomFieldQueryElement,
  CustomFieldQueryAtom,
  CustomFieldQueryExpression,
} from './custom-field-query-element'
import {
  CustomFieldQueryElementType,
  CustomFieldQueryLogicalOperator,
  CustomFieldQueryOperator,
} from '../data/custom-field-query'
import { fakeAsync, tick } from '@angular/core/testing'

describe('CustomFieldQueryElement', () => {
  it('should initialize with correct type and id', () => {
    const element = new CustomFieldQueryElement(
      CustomFieldQueryElementType.Atom
    )
    expect(element.type).toBe(CustomFieldQueryElementType.Atom)
    expect(element.id).toBeDefined()
  })

  it('should trigger changed on operator change', () => {
    const element = new CustomFieldQueryElement(
      CustomFieldQueryElementType.Atom
    )
    element.changed.subscribe((changedElement) => {
      expect(changedElement).toBe(element)
    })
    element.operator = CustomFieldQueryOperator.Exists
  })

  it('should trigger changed subject on value change', () => {
    const element = new CustomFieldQueryElement(
      CustomFieldQueryElementType.Atom
    )
    element.changed.subscribe((changedElement) => {
      expect(changedElement).toBe(element)
    })
    element.value = 'new value'
  })

  it('should throw error on serialize call', () => {
    const element = new CustomFieldQueryElement(
      CustomFieldQueryElementType.Atom
    )
    expect(() => element.serialize()).toThrow('Implemented in subclass')
  })
})

describe('CustomFieldQueryAtom', () => {
  it('should initialize with correct field, operator, and value', () => {
    const atom = new CustomFieldQueryAtom([1, 'operator', 'value'])
    expect(atom.field).toBe(1)
    expect(atom.operator).toBe('operator')
    expect(atom.value).toBe('value')
  })

  it('should trigger changed subject on field change', () => {
    const atom = new CustomFieldQueryAtom()
    atom.changed.subscribe((changedAtom) => {
      expect(changedAtom).toBe(atom)
    })
    atom.field = 2
  })

  it('should set value to null if operator is not found in CUSTOM_FIELD_QUERY_VALUE_TYPES_BY_OPERATOR', () => {
    const atom = new CustomFieldQueryAtom()
    atom.operator = 'nonexistent_operator'
    expect(atom.value).toBeNull()
  })

  it('should set value to empty string if new type is string', () => {
    const atom = new CustomFieldQueryAtom()
    atom.operator = CustomFieldQueryOperator.IContains
    expect(atom.value).toBe('')
  })

  it('should set value to "true" if new type is boolean', () => {
    const atom = new CustomFieldQueryAtom()
    atom.operator = CustomFieldQueryOperator.Exists
    expect(atom.value).toBe('true')
  })

  it('should set value to empty array if new type is array', () => {
    const atom = new CustomFieldQueryAtom()
    atom.operator = CustomFieldQueryOperator.In
    expect(atom.value).toEqual([])
  })

  it('should try to set existing value to number if new type is number', () => {
    const atom = new CustomFieldQueryAtom()
    atom.value = '42'
    atom.operator = CustomFieldQueryOperator.GreaterThan
    expect(atom.value).toBe('42')

    // fallback to null if value is not parseable
    atom.value = 'not_a_number'
    atom.operator = CustomFieldQueryOperator.GreaterThan
    expect(atom.value).toBeNull()
  })

  it('should change boolean values to empty string if operator is not boolean', () => {
    const atom = new CustomFieldQueryAtom()
    atom.value = 'true'
    atom.operator = CustomFieldQueryOperator.Exact
    expect(atom.value).toBe('')
  })

  it('should serialize correctly', () => {
    const atom = new CustomFieldQueryAtom([1, 'operator', 'value'])
    expect(atom.serialize()).toEqual([1, 'operator', 'value'])
  })

  it('should emit changed on value change after debounce', fakeAsync(() => {
    const atom = new CustomFieldQueryAtom()
    const changeSpy = jest.spyOn(atom.changed, 'next')
    atom.value = 'new value'
    tick(1000)
    expect(changeSpy).toHaveBeenCalled()
  }))
})

describe('CustomFieldQueryExpression', () => {
  it('should initialize with default operator and empty value', () => {
    const expression = new CustomFieldQueryExpression()
    expect(expression.operator).toBe(CustomFieldQueryLogicalOperator.Or)
    expect(expression.value).toEqual([])
  })

  it('should initialize with correct operator and value, propagate changes', () => {
    const expression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.And,
      [
        [1, 'exists', 'true'],
        [2, 'exists', 'true'],
      ],
    ])
    expect(expression.operator).toBe(CustomFieldQueryLogicalOperator.And)
    expect(expression.value.length).toBe(2)

    // propagate changes
    const expressionChangeSpy = jest.spyOn(expression.changed, 'next')
    ;(expression.value[0] as CustomFieldQueryAtom).changed.next(
      expression.value[0] as any
    )
    expect(expressionChangeSpy).toHaveBeenCalled()

    const expression2 = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.Not,
      [[CustomFieldQueryLogicalOperator.Or, []]],
    ])
    const expressionChangeSpy2 = jest.spyOn(expression2.changed, 'next')
    ;(expression2.value[0] as CustomFieldQueryExpression).changed.next(
      expression2.value[0] as any
    )
    expect(expressionChangeSpy2).toHaveBeenCalled()
  })

  it('should initialize with a sub-expression i.e. NOT', () => {
    const expression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.Not,
      [
        'AND',
        [
          [1, 'exists', 'true'],
          [2, 'exists', 'true'],
        ],
      ],
    ])
    expect(expression.value).toHaveLength(1)
    const changedSpy = jest.spyOn(expression.changed, 'next')
    ;(expression.value[0] as CustomFieldQueryExpression).changed.next(
      expression.value[0] as any
    )
    expect(changedSpy).toHaveBeenCalled()
  })

  it('should add atom correctly, propagate changes', () => {
    const expression = new CustomFieldQueryExpression()
    const atom = new CustomFieldQueryAtom([
      1,
      CustomFieldQueryOperator.Exists,
      'true',
    ])
    expression.addAtom(atom)
    expect(expression.value).toContain(atom)
    const changeSpy = jest.spyOn(expression.changed, 'next')
    atom.changed.next(atom)
    expect(changeSpy).toHaveBeenCalled()
    // coverage
    expression.addAtom()
  })

  it('should add expression correctly, propagate changes', () => {
    const expression = new CustomFieldQueryExpression()
    const subExpression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.Or,
      [],
    ])
    expression.addExpression(subExpression)
    expect(expression.value).toContain(subExpression)
    const changeSpy = jest.spyOn(expression.changed, 'next')
    subExpression.changed.next(subExpression)
    expect(changeSpy).toHaveBeenCalled()
    // coverage
    expression.addExpression()
  })

  it('should serialize correctly', () => {
    const expression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.And,
      [[1, 'exists', 'true']],
    ])
    expect(expression.serialize()).toEqual([
      CustomFieldQueryLogicalOperator.And,
      [[1, 'exists', 'true']],
    ])
  })

  it('should serialize NOT expressions correctly', () => {
    const expression = new CustomFieldQueryExpression()
    expression.addExpression(
      new CustomFieldQueryExpression([
        CustomFieldQueryLogicalOperator.And,
        [
          [1, 'exists', 'true'],
          [2, 'exists', 'true'],
        ],
      ])
    )
    expression.operator = CustomFieldQueryLogicalOperator.Not
    const serialized = expression.serialize()
    expect(serialized[0]).toBe(CustomFieldQueryLogicalOperator.Not)
    expect(serialized[1][0]).toBe(CustomFieldQueryLogicalOperator.And)
    expect(serialized[1][1].length).toBe(2)
  })

  it('should be negatable if it has one child which is an expression', () => {
    const expression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.Not,
      [[CustomFieldQueryLogicalOperator.Or, []]],
    ])
    expect(expression.negatable).toBe(true)
  })
})
