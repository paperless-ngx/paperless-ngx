import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SimplePaginatorComponent } from './simple-paginator.component';

describe('SimplePaginatorComponent', () => {
  let component: SimplePaginatorComponent;
  let fixture: ComponentFixture<SimplePaginatorComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SimplePaginatorComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(SimplePaginatorComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
