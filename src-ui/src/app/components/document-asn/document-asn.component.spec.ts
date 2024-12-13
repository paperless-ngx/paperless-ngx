import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import { of } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import { FilterRule } from 'src/app/data/filter-rule'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { DocumentService } from 'src/app/services/rest/document.service'
import { DocumentAsnComponent } from './document-asn.component'

describe('DocumentAsnComponent', () => {
  let component: DocumentAsnComponent
  let fixture: ComponentFixture<DocumentAsnComponent>
  let router: Router
  let activatedRoute: ActivatedRoute

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [DocumentAsnComponent],
      providers: [
        {
          provide: DocumentService,
          useValue: {
            listAllFilteredIds: (rules: FilterRule[]) =>
              rules[0].value === '1234' ? of([1]) : of([]),
          },
        },
        PermissionsGuard,
      ],
      imports: [RouterTestingModule.withRoutes(routes)],
    }).compileComponents()

    router = TestBed.inject(Router)
    activatedRoute = TestBed.inject(ActivatedRoute)
    fixture = TestBed.createComponent(DocumentAsnComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should navigate on valid asn', () => {
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ id: '1234' })))
    const navigateSpy = jest.spyOn(router, 'navigate')
    component.ngOnInit()
    expect(navigateSpy).toHaveBeenCalledWith(['documents', 1])
  })

  it('should 404 on invalid asn', () => {
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ id: '5578' })))
    const navigateSpy = jest.spyOn(router, 'navigate')
    component.ngOnInit()
    expect(navigateSpy).toHaveBeenCalledWith(['404'], { replaceUrl: true })
  })
})
