import { Clipboard } from '@angular/cdk/clipboard'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { Title } from '@angular/platform-browser'
import { environment } from 'src/environments/environment'
import { PageHeaderComponent } from './page-header.component'

describe('PageHeaderComponent', () => {
  let component: PageHeaderComponent
  let fixture: ComponentFixture<PageHeaderComponent>
  let titleService: Title
  let clipboard: Clipboard

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [],
      imports: [PageHeaderComponent],
    }).compileComponents()

    titleService = TestBed.inject(Title)
    clipboard = TestBed.inject(Clipboard)
    fixture = TestBed.createComponent(PageHeaderComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should display title + subtitle', () => {
    fixture.componentRef.setInput('title', 'Foo')
    fixture.componentRef.setInput('subTitle', 'Bar')
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('Foo')
    expect(fixture.nativeElement.textContent).toContain('Bar')
  })

  it('should set html title', () => {
    const titleSpy = jest.spyOn(titleService, 'setTitle')
    fixture.componentRef.setInput('title', 'Foo Bar')
    expect(titleSpy).toHaveBeenCalledWith(`Foo Bar - ${environment.appTitle}`)
  })

  it('should copy id to clipboard, reset after 3 seconds', () => {
    jest.useFakeTimers()
    fixture.componentRef.setInput('id', 42)
    jest.spyOn(clipboard, 'copy').mockReturnValue(true)
    component.copyID()
    expect(clipboard.copy).toHaveBeenCalledWith('42')
    expect(component.copied()).toBe(true)

    jest.advanceTimersByTime(3000)
    expect(component.copied()).toBe(false)
  })
})
