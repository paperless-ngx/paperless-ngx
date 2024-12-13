import { ComponentFixture, TestBed } from '@angular/core/testing'
import { Title } from '@angular/platform-browser'
import { environment } from 'src/environments/environment'
import { PageHeaderComponent } from './page-header.component'

describe('PageHeaderComponent', () => {
  let component: PageHeaderComponent
  let fixture: ComponentFixture<PageHeaderComponent>
  let titleService: Title

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [PageHeaderComponent],
      providers: [],
      imports: [],
    }).compileComponents()

    titleService = TestBed.inject(Title)
    fixture = TestBed.createComponent(PageHeaderComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should display title + subtitle', () => {
    component.title = 'Foo'
    component.subTitle = 'Bar'
    fixture.detectChanges()
    expect(fixture.nativeElement.textContent).toContain('Foo Bar')
  })

  it('should set html title', () => {
    const titleSpy = jest.spyOn(titleService, 'setTitle')
    component.title = 'Foo Bar'
    expect(titleSpy).toHaveBeenCalledWith(`Foo Bar - ${environment.appTitle}`)
  })
})
