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

  it('should serialize correctly', () => {
    const atom = new CustomFieldQueryAtom([1, 'operator', 'value'])
    expect(atom.serialize()).toEqual([1, 'operator', 'value'])
  })
})

describe('CustomFieldQueryExpression', () => {
  it('should initialize with correct operator and value', () => {
    const expression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.And,
      [],
    ])
    expect(expression.operator).toBe(CustomFieldQueryLogicalOperator.And)
    expect(expression.value).toEqual([])
  })

  it('should add atom correctly', () => {
    const expression = new CustomFieldQueryExpression()
    const atom = new CustomFieldQueryAtom([
      1,
      CustomFieldQueryOperator.Exists,
      'true',
    ])
    expression.addAtom(atom)
    expect(expression.value).toContain(atom)
  })

  it('should add expression correctly', () => {
    const expression = new CustomFieldQueryExpression()
    const subExpression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.Or,
      [],
    ])
    expression.addExpression(subExpression)
    expect(expression.value).toContain(subExpression)
  })

  it('should serialize correctly', () => {
    const expression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.And,
      [[1, 'operator', 'value']],
    ])
    expect(expression.serialize()).toEqual([
      CustomFieldQueryLogicalOperator.And,
      [[1, 'operator', 'value']],
    ])
  })

  it('should be negatable if it has one child which is an expression', () => {
    const expression = new CustomFieldQueryExpression([
      CustomFieldQueryLogicalOperator.Not,
      [[CustomFieldQueryLogicalOperator.Or, []]],
    ])
    expect(expression.negatable).toBe(true)
  })
})
