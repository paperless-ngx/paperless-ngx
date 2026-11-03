import { ComponentFixture, TestBed } from '@angular/core/testing'
import { BootstrapIconComponent } from './bootstrap-icon.component'

describe('BootstrapIconComponent', () => {
  let fixture: ComponentFixture<BootstrapIconComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [BootstrapIconComponent],
    })
    fixture = TestBed.createComponent(BootstrapIconComponent)
  })

  it('should render the named icon as inline svg', () => {
    fixture.componentRef.setInput('name', 'arrow-down-up')
    fixture.detectChanges()
    const svg: SVGElement = fixture.nativeElement.querySelector('svg')
    expect(svg.classList).toContain('bi-arrow-down-up')
    expect(svg.getAttribute('width')).toEqual('16')
    expect(svg.getAttribute('height')).toEqual('16')
  })

  it('should apply width and height', () => {
    fixture.componentRef.setInput('name', 'x-lg')
    fixture.componentRef.setInput('width', '1.2em')
    fixture.componentRef.setInput('height', 2)
    fixture.detectChanges()
    const svg: SVGElement = fixture.nativeElement.querySelector('svg')
    expect(svg.getAttribute('width')).toEqual('1.2em')
    expect(svg.getAttribute('height')).toEqual('2')
  })

  it('should update when the name changes', () => {
    fixture.componentRef.setInput('name', 'x-lg')
    fixture.detectChanges()
    fixture.componentRef.setInput('name', 'sliders2-vertical')
    fixture.detectChanges()
    expect(fixture.nativeElement.querySelector('svg').classList).toContain(
      'bi-sliders2-vertical'
    )
  })

  it('should render nothing and warn for an unregistered icon', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {})
    fixture.componentRef.setInput('name', 'not-an-icon')
    fixture.detectChanges()
    expect(fixture.nativeElement.innerHTML).toEqual('')
    expect(warnSpy).toHaveBeenCalledWith('Icon not found: not-an-icon')
  })
})
