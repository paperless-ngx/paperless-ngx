import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import {
  FormsModule,
  ReactiveFormsModule,
  NG_VALUE_ACCESSOR,
} from '@angular/forms'
import { SelectComponent } from './select.component'
import { Tag } from 'src/app/data/tag'
import {
  DEFAULT_MATCHING_ALGORITHM,
  MATCH_ALL,
} from 'src/app/data/matching-model'
import { NgSelectModule } from '@ng-select/ng-select'
import { RouterTestingModule } from '@angular/router/testing'

const items: Tag[] = [
  {
    id: 1,
    name: 'Tag1',
    is_inbox_tag: false,
    matching_algorithm: DEFAULT_MATCHING_ALGORITHM,
  },
  {
    id: 2,
    name: 'Tag2',
    is_inbox_tag: true,
    matching_algorithm: MATCH_ALL,
    match: 'str',
  },
  {
    id: 10,
    name: 'Tag10',
    is_inbox_tag: false,
    matching_algorithm: DEFAULT_MATCHING_ALGORITHM,
  },
]

describe('SelectComponent', () => {
  let component: SelectComponent
  let fixture: ComponentFixture<SelectComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [SelectComponent],
      providers: [],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        RouterTestingModule,
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(SelectComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should support private items', () => {
    component.value = 3
    component.items = items
    expect(component.items).toContainEqual({
      id: 3,
      name: 'Private',
      private: true,
    })

    component.checkForPrivateItems([4, 5])
    expect(component.items).toContainEqual({
      id: 4,
      name: 'Private',
      private: true,
    })
    expect(component.items).toContainEqual({
      id: 5,
      name: 'Private',
      private: true,
    })
  })

  it('should support suggestions', () => {
    expect(component.value).toBeUndefined()
    component.items = items
    component.suggestions = [1, 2]
    fixture.detectChanges()
    const suggestionAnchor: HTMLAnchorElement =
      fixture.nativeElement.querySelector('a')
    suggestionAnchor.click()
    expect(component.value).toEqual(1)
  })

  it('should support create new and emit the value', () => {
    expect(component.allowCreateNew).toBeFalsy()
    component.items = items
    let createNewVal
    component.createNew.subscribe((v) => (createNewVal = v))
    expect(component.allowCreateNew).toBeTruthy()
    component.onSearch({ term: 'foo' })
    component.addItem(undefined)
    expect(createNewVal).toEqual('foo')
    component.addItem('bar')
    expect(createNewVal).toEqual('bar')
    component.onSearch({ term: 'baz' })
    component.clickNew()
    expect(createNewVal).toEqual('baz')
  })

  it('should clear search term on blur after delay', fakeAsync(() => {
    const clearSpy = jest.spyOn(component, 'clearLastSearchTerm')
    component.onBlur()
    tick(3000)
    expect(clearSpy).toHaveBeenCalled()
  }))

  it('should emit filtered documents', () => {
    component.value = 10
    component.items = items
    const emitSpy = jest.spyOn(component.filterDocuments, 'emit')
    component.onFilterDocuments()
    expect(emitSpy).toHaveBeenCalledWith([items[2]])
  })

  it('should return the correct filter button title', () => {
    component.title = 'Tag'
    const expectedTitle = `Filter documents with this ${component.title}`
    expect(component.filterButtonTitle).toEqual(expectedTitle)
  })

  it('should support setting items as a plain array', () => {
    component.itemsArray = ['foo', 'bar']
    expect(component.items).toEqual([
      { id: 0, name: 'foo' },
      { id: 1, name: 'bar' },
    ])
  })
})
