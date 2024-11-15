import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  ToggleableDropdownButtonComponent,
  ToggleableItemState,
} from './toggleable-dropdown-button.component'
import { TagComponent } from '../../tag/tag.component'
import { Tag } from 'src/app/data/tag'

describe('ToggleableDropdownButtonComponent', () => {
  let component: ToggleableDropdownButtonComponent
  let fixture: ComponentFixture<ToggleableDropdownButtonComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [ToggleableDropdownButtonComponent, TagComponent],
      providers: [],
      imports: [],
    }).compileComponents()

    fixture = TestBed.createComponent(ToggleableDropdownButtonComponent)
    component = fixture.componentInstance
  })

  it('should recognize a tag', () => {
    component.item = {
      id: 1,
      name: 'Test Tag',
      is_inbox_tag: false,
    } as Tag

    fixture.detectChanges()
    expect(component.isTag).toBeTruthy()
  })

  it('should report toggled state', () => {
    expect(component.isChecked()).toBeFalsy()
    expect(component.isPartiallyChecked()).toBeFalsy()
    expect(component.isExcluded()).toBeFalsy()

    component.state = ToggleableItemState.Selected
    expect(component.isChecked()).toBeTruthy()
    expect(component.isPartiallyChecked()).toBeFalsy()
    expect(component.isExcluded()).toBeFalsy()

    component.state = ToggleableItemState.PartiallySelected
    expect(component.isPartiallyChecked()).toBeTruthy()
    expect(component.isChecked()).toBeFalsy()
    expect(component.isExcluded()).toBeFalsy()

    component.state = ToggleableItemState.Excluded
    expect(component.isExcluded()).toBeTruthy()
    expect(component.isChecked()).toBeFalsy()
    expect(component.isPartiallyChecked()).toBeFalsy()
  })

  it('should emit exclude event when selected and then toggled', () => {
    let excludeResult
    let toggleResult
    component.state = ToggleableItemState.Selected
    component.exclude.subscribe(() => (excludeResult = true))
    component.toggled.subscribe(() => (toggleResult = true))
    const button = fixture.nativeElement.querySelector('button')
    button.dispatchEvent(new MouseEvent('click'))
    expect(excludeResult).toBeTruthy()
    expect(toggleResult).toBeFalsy()
  })

  it('should emit toggle event when not selected and then toggled', () => {
    let excludeResult
    let toggleResult
    component.state = ToggleableItemState.Excluded
    component.exclude.subscribe(() => (excludeResult = true))
    component.toggled.subscribe(() => (toggleResult = true))
    const button = fixture.nativeElement.querySelector('button')
    button.dispatchEvent(new MouseEvent('click'))
    expect(excludeResult).toBeFalsy()
    expect(toggleResult).toBeTruthy()
  })
})
