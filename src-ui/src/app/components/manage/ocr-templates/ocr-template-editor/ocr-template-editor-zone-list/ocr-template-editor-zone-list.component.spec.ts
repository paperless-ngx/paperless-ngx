import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { CustomField } from 'src/app/data/custom-field'
import { OcrTemplateZone } from 'src/app/data/ocr-template'
import { OcrTemplateEditorZoneListComponent } from './ocr-template-editor-zone-list.component'

function zone(overrides: Partial<OcrTemplateZone> = {}): OcrTemplateZone {
  return {
    name: 'Zone 1',
    target: 'custom_field',
    custom_field: 7,
    x: 10,
    y: 20,
    width: 30,
    height: 40,
    page: 1,
    ocr_language: 'eng',
    transform: 'strip',
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

    expect(fixture.nativeElement.textContent).toContain('No zones defined')
  })

  it('renders zone target, size, and page', () => {
    component.zones = [zone()]
    component.customFields = [{ id: 7, name: 'Invoice Number' } as CustomField]
    fixture.detectChanges()

    const text = fixture.nativeElement.textContent
    expect(text).toContain('Zone 1')
    expect(text).toContain('Invoice Number')
    expect(text).toContain('30x40px')
    expect(text).toContain('p.1')
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
