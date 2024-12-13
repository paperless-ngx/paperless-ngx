import { DragDropModule } from '@angular/cdk/drag-drop'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms'
import { DragDropSelectComponent } from './drag-drop-select.component'

describe('DragDropSelectComponent', () => {
  let component: DragDropSelectComponent
  let fixture: ComponentFixture<DragDropSelectComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DragDropModule, FormsModule],
      declarations: [DragDropSelectComponent],
    }).compileComponents()

    fixture = TestBed.createComponent(DragDropSelectComponent)
    component = fixture.componentInstance
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    fixture.detectChanges()
  })

  it('should update selectedItems when writeValue is called', () => {
    const newValue = ['1', '2', '3']
    component.items = [
      { id: '1', name: 'Item 1' },
      { id: '2', name: 'Item 2' },
      { id: '3', name: 'Item 3' },
    ]
    component.writeValue(newValue)
    expect(component.selectedItems).toEqual([
      { id: '1', name: 'Item 1' },
      { id: '2', name: 'Item 2' },
      { id: '3', name: 'Item 3' },
    ])

    component.writeValue(null)
    expect(component.selectedItems).toEqual([])
  })

  it('should update selectedItems when an item is dropped within selectedList', () => {
    component.items = [
      { id: '1', name: 'Item 1' },
      { id: '2', name: 'Item 2' },
      { id: '3', name: 'Item 3' },
      { id: '4', name: 'Item 4' },
    ]
    component.writeValue(['1', '2', '3'])
    const event = {
      previousContainer: component.selectedList,
      container: component.selectedList,
      previousIndex: 1,
      currentIndex: 2,
    }
    component.drop(event as any)
    expect(component.selectedItems).toEqual([
      { id: '1', name: 'Item 1' },
      { id: '3', name: 'Item 3' },
      { id: '2', name: 'Item 2' },
    ])
  })

  it('should update selectedItems when an item is dropped from unselectedList to selectedList', () => {
    component.items = [
      { id: '1', name: 'Item 1' },
      { id: '2', name: 'Item 2' },
      { id: '3', name: 'Item 3' },
    ]
    component.writeValue(['1', '2'])
    const event = {
      previousContainer: component.unselectedList,
      container: component.selectedList,
      previousIndex: 0,
      currentIndex: 2,
    }
    component.drop(event as any)
    expect(component.selectedItems).toEqual([
      { id: '1', name: 'Item 1' },
      { id: '2', name: 'Item 2' },
      { id: '3', name: 'Item 3' },
    ])
  })

  it('should update selectedItems when an item is dropped from selectedList to unselectedList', () => {
    component.items = [
      { id: '1', name: 'Item 1' },
      { id: '2', name: 'Item 2' },
      { id: '3', name: 'Item 3' },
    ]
    component.writeValue(['1', '2', '3'])
    const event = {
      previousContainer: component.selectedList,
      container: component.unselectedList,
      previousIndex: 1,
      currentIndex: 0,
    }
    component.drop(event as any)
    expect(component.selectedItems).toEqual([
      { id: '1', name: 'Item 1' },
      { id: '3', name: 'Item 3' },
    ])
  })
})
