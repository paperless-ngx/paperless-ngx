import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { EntriesComponent } from './entries.component'

describe('EntriesComponent', () => {
  let component: EntriesComponent
  let fixture: ComponentFixture<EntriesComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [EntriesComponent],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()
  })

  beforeEach(() => {
    fixture = TestBed.createComponent(EntriesComponent)
    component = fixture.componentInstance
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    fixture.detectChanges()
  })

  it('should add an entry', () => {
    component.addEntry()
    expect(component.entries.length).toBe(1)
    expect(component.entries[0]).toEqual(['', ''])
  })

  it('should remove an entry', () => {
    component.addEntry()
    component.addEntry()
    expect(component.entries.length).toBe(2)
    component.removeEntry(0)
    expect(component.entries.length).toBe(1)
  })

  it('should write value correctly', () => {
    const newValue = { key1: 'value1', key2: 'value2' }
    component.writeValue(newValue)
    expect(component.entries).toEqual(Object.entries(newValue))
    component.writeValue(null)
    expect(component.entries).toEqual([])
  })

  it('should correctly generate the value on input change', () => {
    const onChangeSpy = jest.spyOn(component, 'onChange')
    component.entries = [
      ['key1', 'value1'],
      ['key2', ''],
      ['', ''],
    ]
    component.inputChange()
    // Only the first two entries should be included
    expect(onChangeSpy).toHaveBeenCalledWith({ key1: 'value1', key2: '' })
  })
})
