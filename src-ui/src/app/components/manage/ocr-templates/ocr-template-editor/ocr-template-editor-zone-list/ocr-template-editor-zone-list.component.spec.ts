import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { CustomField } from 'src/app/data/custom-field'
import {
  OcrTemplateZone,
  OcrZoneTarget,
  OcrZoneTransform,
} from 'src/app/data/ocr-template'
import { OcrTemplateEditorZoneListComponent } from './ocr-template-editor-zone-list.component'

function zone(overrides: Partial<OcrTemplateZone> = {}): OcrTemplateZone {
  return {
    name: 'Zone 1',
    target: OcrZoneTarget.CustomField,
    custom_field: 7,
    x: 10,
    y: 20,
    width: 30,
    height: 40,
    page: 1,
    ocr_language: 'eng',
    transform: OcrZoneTransform.Strip,
    validation_regex: '',
    order: 0,
    ...overrides,
  }
}

describe('OcrTemplateEditorZoneListComponent', () => {
  let fixture: ComponentFixture<OcrTemplateEditorZoneListComponent>
  let component: OcrTemplateEditorZoneListComponent

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        OcrTemplateEditorZoneListComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(OcrTemplateEditorZoneListComponent)
    component = fixture.componentInstance
  })

  it('shows empty state when no zones are defined', () => {
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain('No zones yet')
  })

  it('renders zone name, target, and page', () => {
    component.zones = [zone(), zone({ name: 'Zone 2', page: -1 })]
    component.customFields = [{ id: 7, name: 'Invoice Number' } as CustomField]
    fixture.detectChanges()

    const text = fixture.nativeElement.textContent
    expect(text).toContain('Zone 1')
    expect(text).toContain('Invoice Number')
    expect(text).toContain('Page 1')
    expect(text).toContain('Last page')
  })

  it('marks zones that share a field', () => {
    component.zones = [
      zone(),
      zone({ name: 'Zone 2' }),
      zone({ name: 'Zone 3', custom_field: 8 }),
    ]
    fixture.detectChanges()

    expect(component.isCombined(component.zones[0])).toBe(true)
    expect(component.isCombined(component.zones[2])).toBe(false)
    expect(
      fixture.nativeElement.querySelectorAll(
        '[title="Combined with other zones"]'
      ).length
    ).toBe(2)
  })

  it('warns only for zones without a field and clears the warning when assigned', () => {
    component.zones = [
      zone({ custom_field: null }),
      zone({ target: OcrZoneTarget.Title, custom_field: null }),
      zone(),
    ]
    fixture.detectChanges()

    const warnings = () =>
      fixture.nativeElement.querySelectorAll('.text-warning')
    expect(warnings()).toHaveLength(1)
    expect(warnings()[0].textContent).toContain('No field selected')

    component.zones[0].custom_field = 7
    fixture.componentRef.setInput('zones', [...component.zones])
    fixture.detectChanges()
    expect(warnings()).toHaveLength(0)
  })

  it('emits select and remove events', () => {
    component.zones = [zone()]
    const selectSpy = jest.spyOn(component.zoneSelected, 'emit')
    const removeSpy = jest.spyOn(component.zoneRemoved, 'emit')
    fixture.detectChanges()

    const buttons = fixture.nativeElement.querySelectorAll('button')
    buttons[0].click()
    buttons[1].click()

    expect(selectSpy).toHaveBeenCalledWith(0)
    expect(removeSpy).toHaveBeenCalledWith(0)
  })
})
