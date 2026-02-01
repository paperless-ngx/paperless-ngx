import { ScrollingModule } from '@angular/cdk/scrolling'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { NEGATIVE_NULL_FILTER_VALUE } from 'src/app/data/filter-rule-type'
import {
  DEFAULT_MATCHING_ALGORITHM,
  MATCH_ALL,
} from 'src/app/data/matching-model'
import { Tag } from 'src/app/data/tag'
import { FilterPipe } from 'src/app/pipes/filter.pipe'
import { HotKeyService } from 'src/app/services/hot-key.service'
import {
  ChangedItems,
  FilterableDropdownComponent,
  FilterableDropdownSelectionModel,
  Intersection,
  LogicalOperator,
} from './filterable-dropdown.component'
import { ToggleableItemState } from './toggleable-dropdown-button/toggleable-dropdown-button.component'

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
]

const nullItem = {
  id: null,
  name: 'Not assigned',
}

const negativeNullItem = {
  id: NEGATIVE_NULL_FILTER_VALUE,
  name: 'Not assigned',
}

let selectionModel: FilterableDropdownSelectionModel

describe('FilterableDropdownComponent & FilterableDropdownSelectionModel', () => {
  let component: FilterableDropdownComponent
  let fixture: ComponentFixture<FilterableDropdownComponent>
  let hotkeyService: HotKeyService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        FilterPipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
      imports: [NgxBootstrapIconsModule.pick(allIcons), ScrollingModule],
    }).compileComponents()

    hotkeyService = TestBed.inject(HotKeyService)
    fixture = TestBed.createComponent(FilterableDropdownComponent)
    component = fixture.componentInstance
    component.selectionModel = new FilterableDropdownSelectionModel()
    selectionModel = new FilterableDropdownSelectionModel()
  })

  it('should sanitize title', () => {
    expect(component.name).toBeNull()
    component.title = 'Foo Bar'
    expect(component.name).toEqual('foo_bar')
  })

  it('should support reset', () => {
    component.selectionModel.items = items
    component.selectionModel = selectionModel
    selectionModel.set(items[0].id, ToggleableItemState.Selected)
    expect(selectionModel.getSelectedItems()).toHaveLength(1)
    expect(selectionModel.isDirty()).toBeTruthy()
    component.reset()
    expect(selectionModel.getSelectedItems()).toHaveLength(0)
    expect(selectionModel.isDirty()).toBeFalsy()
  })

  it('should report document counts', () => {
    component.documentCounts = [
      {
        id: items[0].id,
        document_count: 12,
      },
    ]
    expect(component.getUpdatedDocumentCount(items[0].id)).toEqual(12)
    expect(component.getUpdatedDocumentCount(items[1].id)).toBeUndefined() // coverate of optional chaining
  })

  it('should emit change when items selected', () => {
    component.selectionModel.items = items
    component.selectionModel = selectionModel
    let newModel: FilterableDropdownSelectionModel
    component.selectionModelChange.subscribe((model) => (newModel = model))
    expect(newModel).toBeUndefined()

    selectionModel.set(items[0].id, ToggleableItemState.Selected)
    expect(selectionModel.isDirty()).toBeTruthy()
    expect(newModel.getSelectedItems()).toEqual([items[0]])
    expect(newModel.getExcludedItems()).toEqual([])

    selectionModel.set(items[0].id, ToggleableItemState.NotSelected)
    expect(newModel.getSelectedItems()).toEqual([])

    expect(component.selectionModel.items).toEqual([nullItem, ...items])
  })

  it('should emit change when items excluded', () => {
    component.selectionModel.items = items
    component.selectionModel = selectionModel
    let newModel: FilterableDropdownSelectionModel
    component.selectionModelChange.subscribe((model) => (newModel = model))
    expect(newModel).toBeUndefined()
    selectionModel.toggle(items[0].id)
    expect(newModel.getSelectedItems()).toEqual([items[0]])
  })

  it('should emit change when items excluded', () => {
    component.selectionModel.items = items
    component.selectionModel = selectionModel
    let newModel: FilterableDropdownSelectionModel
    component.selectionModelChange.subscribe((model) => (newModel = model))

    selectionModel.set(items[0].id, ToggleableItemState.Excluded)
    expect(newModel.getSelectedItems()).toEqual([])
    expect(newModel.getExcludedItems()).toEqual([items[0]])

    selectionModel.set(items[0].id, ToggleableItemState.NotSelected)
    expect(newModel.getSelectedItems()).toEqual([])
    expect(newModel.getExcludedItems()).toEqual([])
  })

  it('should exclude items when excluded and not editing', () => {
    component.selectionModel.items = items
    component.selectionModel.manyToOne = true
    component.selectionModel = selectionModel
    selectionModel.set(items[0].id, ToggleableItemState.Selected)
    component.excludeClicked(items[0].id)
    expect(selectionModel.getSelectedItems()).toEqual([])
    expect(selectionModel.getExcludedItems()).toEqual([items[0]])
  })

  it('should toggle when items excluded and editing', () => {
    component.selectionModel.items = items
    component.selectionModel.manyToOne = true
    component.editing = true
    component.selectionModel = selectionModel
    selectionModel.set(items[0].id, ToggleableItemState.NotSelected)
    component.excludeClicked(items[0].id)
    expect(selectionModel.getSelectedItems()).toEqual([items[0]])
    expect(selectionModel.getExcludedItems()).toEqual([])
  })

  it('should hide count for item if adding will increase size of set', () => {
    component.selectionModel.items = items
    component.selectionModel.manyToOne = true
    component.selectionModel = selectionModel
    expect(component.hideCount(items[0])).toBeFalsy()
    selectionModel.logicalOperator = LogicalOperator.Or
    expect(component.hideCount(items[0])).toBeTruthy()
  })

  it('should enforce single select when editing', () => {
    component.editing = true
    component.selectionModel.items = items
    component.selectionModel = selectionModel
    let newModel: FilterableDropdownSelectionModel
    component.selectionModelChange.subscribe((model) => (newModel = model))

    expect(selectionModel.singleSelect).toEqual(true)
    selectionModel.toggle(items[0].id)
    selectionModel.toggle(items[1].id)
    expect(newModel.getSelectedItems()).toEqual([items[1]])
  })

  it('should support manyToOne selecting', () => {
    component.selectionModel.items = items
    selectionModel.manyToOne = false
    component.selectionModel = selectionModel
    component.selectionModel.manyToOne = true
    expect(component.selectionModel.manyToOne).toBeTruthy()
    let newModel: FilterableDropdownSelectionModel
    component.selectionModelChange.subscribe((model) => (newModel = model))

    expect(selectionModel.singleSelect).toEqual(false)
    selectionModel.toggle(items[0].id)
    selectionModel.toggle(items[1].id)
    expect(newModel.getSelectedItems()).toEqual([items[0], items[1]])
  })

  it('should dynamically enable / disable modifier toggle', () => {
    component.selectionModel.items = items
    component.selectionModel = selectionModel
    expect(component.modifierToggleEnabled).toBeTruthy()
    component.selectionModel.manyToOne = true
    expect(component.modifierToggleEnabled).toBeFalsy()
    selectionModel.toggle(items[0].id)
    selectionModel.toggle(items[1].id)
    expect(component.modifierToggleEnabled).toBeTruthy()
  })

  it('should apply changes and close when apply button clicked', () => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    component.editing = true
    component.selectionModel = selectionModel
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    selectionModel.toggle(items[0].id)
    fixture.detectChanges()
    expect(component.modelIsDirty).toBeTruthy()
    let applyResult: ChangedItems
    const closeSpy = jest.spyOn(component.dropdown, 'close')
    component.apply.subscribe((result) => (applyResult = result))
    const applyButton = Array.from(
      (fixture.nativeElement as HTMLDivElement).querySelectorAll('button')
    ).find((b) => b.textContent.includes('Apply'))
    applyButton.dispatchEvent(new MouseEvent('click'))
    expect(closeSpy).toHaveBeenCalled()
    expect(applyResult).toEqual({ itemsToAdd: [items[0]], itemsToRemove: [] })
  })

  it('should apply on close if enabled', () => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    component.editing = true
    component.applyOnClose = true
    component.selectionModel = selectionModel
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    selectionModel.toggle(items[0].id)
    fixture.detectChanges()
    expect(component.modelIsDirty).toBeTruthy()
    let applyResult: ChangedItems
    component.apply.subscribe((result) => (applyResult = result))
    component.dropdown.close()
    expect(applyResult).toEqual({ itemsToAdd: [items[0]], itemsToRemove: [] })
  })

  it('should focus text filter on open, support filtering, clear on close', fakeAsync(() => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)
    expect(document.activeElement).toEqual(
      component.listFilterTextInput.nativeElement
    )
    expect(component.buttonsViewport.getRenderedRange().end).toEqual(3) // all items shown

    component.filterText = 'Tag2'
    fixture.detectChanges()
    expect(component.buttonsViewport.getRenderedRange().end).toEqual(1) // filtered
    component.dropdown.close()
    expect(component.filterText).toHaveLength(0)
  }))

  it('should toggle & close on enter inside filter field if 1 item remains', fakeAsync(() => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    expect(component.selectionModel.getSelectedItems()).toEqual([])
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)
    component.filterText = 'Tag2'
    fixture.detectChanges()
    const closeSpy = jest.spyOn(component.dropdown, 'close')
    component.listFilterTextInput.nativeElement.dispatchEvent(
      new KeyboardEvent('keyup', { key: 'Enter' })
    )
    expect(component.selectionModel.getSelectedItems()).toEqual([items[1]])
    tick(300)
    expect(closeSpy).toHaveBeenCalled()
  }))

  it('should apply & close on enter inside filter field if 1 item remains if editing', fakeAsync(() => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    component.editing = true
    let applyResult: ChangedItems
    component.apply.subscribe((result) => (applyResult = result))
    expect(component.selectionModel.getSelectedItems()).toEqual([])
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)
    component.filterText = 'Tag2'
    fixture.detectChanges()
    component.listFilterTextInput.nativeElement.dispatchEvent(
      new KeyboardEvent('keyup', { key: 'Enter' })
    )
    expect(component.selectionModel.getSelectedItems()).toEqual([items[1]])
    tick(300)
    expect(applyResult).toEqual({ itemsToAdd: [items[1]], itemsToRemove: [] })
  }))

  it('should support arrow keyboard navigation', fakeAsync(() => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)
    component.buttonsViewport?.checkViewportSize()
    fixture.detectChanges()
    const filterInputEl: HTMLInputElement =
      component.listFilterTextInput.nativeElement
    expect(document.activeElement).toEqual(filterInputEl)
    const itemButtons = Array.from(
      (fixture.nativeElement as HTMLDivElement).querySelectorAll('button')
    ).filter((b) => b.textContent.includes('Tag'))
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
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)
    component.buttonsViewport?.checkViewportSize()
    fixture.detectChanges()
    const filterInputEl: HTMLInputElement =
      component.listFilterTextInput.nativeElement
    expect(document.activeElement).toEqual(filterInputEl)
    const itemButtons = Array.from(
      (fixture.nativeElement as HTMLDivElement).querySelectorAll('button')
    ).filter((b) => b.textContent.includes('Tag'))
    filterInputEl.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', bubbles: true })
    )
    itemButtons[0].focus() // normally handled by browser
    itemButtons[0].dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', bubbles: true })
    )
    itemButtons[1].focus() // normally handled by browser
    itemButtons[1].dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'Tab',
        shiftKey: true,
        bubbles: true,
      })
    )
    itemButtons[0].focus() // normally handled by browser
    itemButtons[0].dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    )
    expect(document.activeElement).toEqual(itemButtons[1])
  }))

  it('should support arrow keyboard navigation after click', fakeAsync(() => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)
    component.buttonsViewport?.checkViewportSize()
    fixture.detectChanges()
    const filterInputEl: HTMLInputElement =
      component.listFilterTextInput.nativeElement
    expect(document.activeElement).toEqual(filterInputEl)
    const itemButtons = Array.from(
      (fixture.nativeElement as HTMLDivElement).querySelectorAll('button')
    ).filter((b) => b.textContent.includes('Tag'))
    fixture.nativeElement
      .querySelector('pngx-toggleable-dropdown-button')
      .dispatchEvent(new MouseEvent('click'))
    itemButtons[0].focus() // normally handled by browser
    expect(document.activeElement).toEqual(itemButtons[0])
    itemButtons[0].dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    )
    expect(document.activeElement).toEqual(itemButtons[1])
  }))

  it('should toggle logical operator', fakeAsync(() => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    component.selectionModel.manyToOne = true
    selectionModel.set(items[0].id, ToggleableItemState.Selected)
    selectionModel.set(items[1].id, ToggleableItemState.Selected)
    component.selectionModel = selectionModel
    let changedResult: FilterableDropdownSelectionModel
    component.selectionModelChange.subscribe(
      (result) => (changedResult = result)
    )

    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)

    expect(component.modifierToggleEnabled).toBeTruthy()
    const operatorButtons: HTMLInputElement[] = Array.from(
      (fixture.nativeElement as HTMLDivElement).querySelectorAll('input')
    ).filter((b) => ['and', 'or'].includes(b.value))
    expect(operatorButtons[0].checked).toBeTruthy()
    operatorButtons[1].dispatchEvent(new MouseEvent('click'))
    fixture.detectChanges()
    expect(selectionModel.logicalOperator).toEqual(LogicalOperator.Or)
    expect(changedResult.logicalOperator).toEqual(LogicalOperator.Or)
  }))

  it('should toggle intersection include / exclude', fakeAsync(() => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    selectionModel.set(items[0].id, ToggleableItemState.Selected)
    selectionModel.set(items[1].id, ToggleableItemState.Selected)
    component.selectionModel = selectionModel
    let changedResult: FilterableDropdownSelectionModel
    component.selectionModelChange.subscribe(
      (result) => (changedResult = result)
    )

    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)

    expect(component.modifierToggleEnabled).toBeTruthy()
    const intersectionButtons: HTMLInputElement[] = Array.from(
      (fixture.nativeElement as HTMLDivElement).querySelectorAll('input')
    ).filter((b) => ['include', 'exclude'].includes(b.value))
    expect(intersectionButtons[0].checked).toBeTruthy()
    intersectionButtons[1].dispatchEvent(new MouseEvent('click'))
    fixture.detectChanges()
    expect(selectionModel.intersection).toEqual(Intersection.Exclude)
    expect(changedResult.intersection).toEqual(Intersection.Exclude)
    expect(changedResult.getSelectedItems()).toEqual([])
    expect(changedResult.getExcludedItems()).toEqual(items)
  }))

  it('should update null item selection on toggleIntersection', () => {
    component.selectionModel.items = items
    component.selectionModel = selectionModel
    component.selectionModel.intersection = Intersection.Include
    component.selectionModel.set(null, ToggleableItemState.Selected)
    component.selectionModel.intersection = Intersection.Exclude
    component.selectionModel.toggleIntersection()
    expect(component.selectionModel.getExcludedItems()).toEqual([
      negativeNullItem,
    ])

    component.selectionModel.intersection = Intersection.Include
    component.selectionModel.toggleIntersection()
    expect(component.selectionModel.getSelectedItems()).toEqual([nullItem])
  })

  it('selection model should sort items by state', () => {
    component.selectionModel = selectionModel
    component.selectionModel.items = items.concat([{ id: 3, name: 'Item3' }])
    selectionModel.toggle(items[1].id)
    selectionModel.apply()
    expect(selectionModel.items.length).toEqual(4)
    expect(selectionModel.items).toEqual([
      nullItem,
      items[1],
      { id: 3, name: 'Item3' },
      items[0],
    ])

    selectionModel.intersection = Intersection.Exclude
    selectionModel.toggleIntersection()
    selectionModel.apply()
    expect(selectionModel.items).toEqual([
      negativeNullItem,
      items[1],
      { id: 3, name: 'Item3' },
      items[0],
    ])

    // coverage
    selectionModel.items = selectionModel.items.reverse()
    selectionModel.apply()
  })

  it('selection model should sort items by state and document counts = 0, if set', () => {
    const tagA = { id: 4, name: 'Tag A' }
    component.selectionModel.items = items.concat([tagA])
    component.selectionModel = selectionModel
    component.documentCounts = [
      { id: 1, document_count: 0 }, // Tag1
      { id: 2, document_count: 1 }, // Tag2
      { id: 4, document_count: 2 }, // Tag A
    ]
    component.selectionModel.apply()
    expect(selectionModel.items).toEqual([
      nullItem,
      tagA,
      items[1], // Tag2
      items[0], // Tag1
    ])

    selectionModel.toggle(items[1].id)
    component.documentCounts = [
      { id: 1, document_count: 0 },
      { id: 2, document_count: 1 },
      { id: 4, document_count: 0 },
    ]
    selectionModel.apply()
    expect(selectionModel.items).toEqual([
      nullItem,
      items[1], // Tag2
      tagA,
      items[0], // Tag1
    ])
  })

  it('keeps children with their parent when parent has document count', () => {
    const parent: Tag = {
      id: 10,
      name: 'Parent Tag',
      orderIndex: 0,
      document_count: 2,
    }
    const child: Tag = {
      id: 11,
      name: 'Child Tag',
      parent: parent.id,
      orderIndex: 1,
      document_count: 0,
    }
    const otherRoot: Tag = {
      id: 20,
      name: 'Other Tag',
      orderIndex: 2,
      document_count: 0,
    }

    component.selectionModel.items = [parent, child, otherRoot]
    component.selectionModel = selectionModel
    component.documentCounts = [
      { id: parent.id, document_count: 2 },
      { id: otherRoot.id, document_count: 0 },
    ]
    selectionModel.apply()

    expect(component.selectionModel.items).toEqual([
      nullItem,
      parent,
      child,
      otherRoot,
    ])
  })

  it('keeps selected branches ahead of document-based ordering', () => {
    const selectedRoot: Tag = {
      id: 30,
      name: 'Selected Root',
      orderIndex: 0,
      document_count: 0,
    }
    const otherRoot: Tag = {
      id: 40,
      name: 'Other Root',
      orderIndex: 1,
      document_count: 2,
    }

    component.selectionModel.items = [selectedRoot, otherRoot]
    component.selectionModel = selectionModel
    selectionModel.set(selectedRoot.id, ToggleableItemState.Selected)
    component.documentCounts = [
      { id: selectedRoot.id, document_count: 0 },
      { id: otherRoot.id, document_count: 2 },
    ]
    selectionModel.apply()

    expect(component.selectionModel.items).toEqual([
      nullItem,
      selectedRoot,
      otherRoot,
    ])
  })

  it('resorts items immediately when document count sorting enabled', () => {
    const apple: Tag = { id: 55, name: 'Apple' }
    const zebra: Tag = { id: 56, name: 'Zebra' }

    selectionModel.documentCountSortingEnabled = true
    selectionModel.items = [apple, zebra]
    expect(selectionModel.items.map((item) => item?.id ?? null)).toEqual([
      null,
      apple.id,
      zebra.id,
    ])

    selectionModel.documentCounts = [
      { id: zebra.id, document_count: 5 },
      { id: apple.id, document_count: 0 },
    ]

    expect(selectionModel.items.map((item) => item?.id ?? null)).toEqual([
      null,
      zebra.id,
      apple.id,
    ])
  })

  it('does not resort items by default when document counts are set', () => {
    const first: Tag = { id: 57, name: 'First' }
    const second: Tag = { id: 58, name: 'Second' }

    selectionModel.items = [first, second]
    selectionModel.documentCounts = [
      { id: second.id, document_count: 10 },
      { id: first.id, document_count: 0 },
    ]

    expect(selectionModel.items.map((item) => item?.id ?? null)).toEqual([
      null,
      first.id,
      second.id,
    ])
  })

  it('uses fallback document counts when selection data is missing', () => {
    const fallbackRoot: Tag = {
      id: 50,
      name: 'Fallback Root',
      orderIndex: 0,
      document_count: 3,
    }
    const fallbackChild: Tag = {
      id: 51,
      name: 'Fallback Child',
      parent: fallbackRoot.id,
      orderIndex: 1,
      document_count: 0,
    }
    const otherRoot: Tag = {
      id: 60,
      name: 'Other Root',
      orderIndex: 2,
      document_count: 0,
    }

    component.selectionModel = selectionModel
    selectionModel.items = [fallbackRoot, fallbackChild, otherRoot]
    component.documentCounts = [{ id: otherRoot.id, document_count: 0 }]

    selectionModel.apply()

    expect(selectionModel.items).toEqual([
      nullItem,
      fallbackRoot,
      fallbackChild,
      otherRoot,
    ])
  })

  it('handles special and non-numeric ids when promoting branches', () => {
    const rootWithDocs: Tag = {
      id: 70,
      name: 'Root With Docs',
      orderIndex: 0,
      document_count: 1,
    }
    const miscItem: any = { id: 'misc', name: 'Misc Item' }

    component.selectionModel = selectionModel
    selectionModel.intersection = Intersection.Exclude
    selectionModel.items = [rootWithDocs, miscItem as any]
    component.documentCounts = [{ id: rootWithDocs.id, document_count: 1 }]

    selectionModel.apply()

    expect(selectionModel.items.map((item) => item.id)).toEqual([
      NEGATIVE_NULL_FILTER_VALUE,
      rootWithDocs.id,
      'misc',
    ])
  })

  it('memoizes root document counts between lookups', () => {
    const memoRoot: Tag = { id: 80, name: 'Memo Root' }
    selectionModel.items = [memoRoot]
    selectionModel.documentCounts = [{ id: memoRoot.id, document_count: 9 }]

    const getRootDocCount = (selectionModel as any).createRootDocCounter()

    expect(getRootDocCount(memoRoot.id)).toEqual(9)
    selectionModel.documentCounts = []
    expect(getRootDocCount(memoRoot.id)).toEqual(9)
  })

  it('falls back to model stored document counts if selection data missing entry', () => {
    const rootWithoutSelection: Tag = {
      id: 90,
      name: 'Fallback Root',
      document_count: 4,
    }
    selectionModel.items = [rootWithoutSelection]
    selectionModel.documentCounts = []

    const getRootDocCount = (selectionModel as any).createRootDocCounter()

    expect(getRootDocCount(rootWithoutSelection.id)).toEqual(4)
  })

  it('defaults to zero document count when neither selection nor model provide it', () => {
    const rootWithoutCounts: Tag = { id: 91, name: 'Fallback Zero Root' }
    selectionModel.items = [rootWithoutCounts]
    selectionModel.documentCounts = []

    const getRootDocCount = (selectionModel as any).createRootDocCounter()

    expect(getRootDocCount(rootWithoutCounts.id)).toEqual(0)
  })

  it('should set support create, keep open model and call createRef method', fakeAsync(() => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    component.selectionModel = selectionModel
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    tick(100)

    component.filterText = 'Test Filter Text'
    component.createRef = jest.fn()
    component.createClicked()
    expect(component.creating).toBeTruthy()
    expect(component.createRef).toHaveBeenCalledWith('Test Filter Text')
    const openSpy = jest.spyOn(component.dropdown, 'open')
    component.dropdownOpenChange(false)
    expect(openSpy).toHaveBeenCalled() // should keep open
  }))

  it('should call create on enter inside filter field if 0 items remain while editing', fakeAsync(() => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    component.editing = true
    component.createRef = jest.fn()
    const createSpy = jest.spyOn(component, 'createClicked')
    expect(component.selectionModel.getSelectedItems()).toEqual([])
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    tick(100)
    component.filterText = 'FooBar'
    component.listFilterEnter()
    expect(component.selectionModel.getSelectedItems()).toEqual([])
    expect(createSpy).toHaveBeenCalled()
  }))

  it('should exclude item and trigger change event', () => {
    const id = 1
    const state = ToggleableItemState.Selected
    component.selectionModel = selectionModel
    component.selectionModel.manyToOne = true
    component.selectionModel.singleSelect = true
    component.selectionModel.intersection = Intersection.Include
    component.selectionModel['temporarySelectionStates'].set(id, state)
    const changedSpy = jest.spyOn(component.selectionModel.changed, 'next')
    component.selectionModel.exclude(id)
    expect(component.selectionModel.temporaryLogicalOperator).toBe(
      LogicalOperator.And
    )
    expect(component.selectionModel['temporarySelectionStates'].get(id)).toBe(
      ToggleableItemState.Excluded
    )
    expect(component.selectionModel['temporarySelectionStates'].size).toBe(1)
    expect(changedSpy).toHaveBeenCalled()
  })

  it('should initialize selection states and apply changes', () => {
    selectionModel.items = items
    const map = new Map<number, ToggleableItemState>()
    map.set(1, ToggleableItemState.Selected)
    map.set(2, ToggleableItemState.Excluded)
    selectionModel.init(map)
    expect(selectionModel.getSelectedItems()).toEqual([items[0]])
    expect(selectionModel.getExcludedItems()).toEqual([items[1]])
  })

  it('should support shortcut keys', () => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    component.shortcutKey = 't'
    fixture.detectChanges()
    const openSpy = jest.spyOn(component.dropdown, 'open')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 't' }))
    expect(openSpy).toHaveBeenCalled()
  })

  it('should support an extra button and not apply changes when clicked', () => {
    component.selectionModel.items = items
    component.icon = 'tag-fill'
    component.extraButtonTitle = 'Extra'
    component.selectionModel = selectionModel
    component.applyOnClose = true
    let extraButtonClicked,
      applied = false
    component.extraButton.subscribe(() => (extraButtonClicked = true))
    component.apply.subscribe(() => (applied = true))
    fixture.nativeElement
      .querySelector('button')
      .dispatchEvent(new MouseEvent('click')) // open
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain('Extra')
    component.extraButtonClicked()
    expect(extraButtonClicked).toBeTruthy()
    expect(applied).toBeFalsy()
  })
})
