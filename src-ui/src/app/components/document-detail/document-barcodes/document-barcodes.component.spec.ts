import { Clipboard } from '@angular/cdk/clipboard'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { DocumentBarcodesComponent } from './document-barcodes.component'

const barcodes = [
  { page: 1, value: 'ASN00123', format: 'Code 128' },
  { page: 2, value: 'https://example.com/invoice/4711', format: 'QR Code' },
  { page: 2, value: 'javascript:alert(1)', format: 'QR Code' },
]

describe('DocumentBarcodesComponent', () => {
  let component: DocumentBarcodesComponent
  let fixture: ComponentFixture<DocumentBarcodesComponent>
  let clipboard: Clipboard

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        DocumentBarcodesComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(DocumentBarcodesComponent)
    component = fixture.componentInstance
    clipboard = TestBed.inject(Clipboard)
    fixture.componentRef.setInput('barcodes', barcodes)
    fixture.detectChanges()
  })

  it('should display all barcodes', () => {
    const rows = fixture.nativeElement.querySelectorAll('tbody tr')
    expect(rows).toHaveLength(3)
    expect(rows[0].textContent).toContain('ASN00123')
    expect(rows[0].textContent).toContain('Code 128')
  })

  it('should only link http(s) values', () => {
    const links = fixture.nativeElement.querySelectorAll('tbody a')
    expect(links).toHaveLength(1)
    expect(links[0].getAttribute('href')).toEqual(
      'https://example.com/invoice/4711'
    )
    expect(links[0].getAttribute('target')).toEqual('_blank')
  })

  it('should copy a value and show feedback', () => {
    jest.useFakeTimers()
    const copySpy = jest.spyOn(clipboard, 'copy').mockReturnValue(true)
    const buttons = fixture.nativeElement.querySelectorAll('tbody button')
    buttons[0].click()
    fixture.detectChanges()
    expect(copySpy).toHaveBeenCalledWith('ASN00123')
    expect(component.copiedIndex()).toEqual(0)
    expect(buttons[0].querySelector('i-bs').getAttribute('name')).toEqual(
      'clipboard-check'
    )
    jest.advanceTimersByTime(3000)
    fixture.detectChanges()
    expect(component.copiedIndex()).toBeNull()
    expect(buttons[0].querySelector('i-bs').getAttribute('name')).toEqual(
      'clipboard'
    )
    jest.useRealTimers()
  })

  it('should not show feedback if copying failed', () => {
    jest.spyOn(clipboard, 'copy').mockReturnValue(false)
    component.copy(1)
    expect(component.copiedIndex()).toBeNull()
  })
})
