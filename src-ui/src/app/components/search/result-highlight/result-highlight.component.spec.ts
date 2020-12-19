import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ResultHighlightComponent } from './result-highlight.component';

describe('ResultHighlightComponent', () => {
  let component: ResultHighlightComponent;
  let fixture: ComponentFixture<ResultHighlightComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ResultHighlightComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ResultHighlightComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
