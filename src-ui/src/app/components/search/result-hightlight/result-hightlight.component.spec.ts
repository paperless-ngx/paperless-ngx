import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ResultHightlightComponent } from './result-hightlight.component';

describe('ResultHightlightComponent', () => {
  let component: ResultHightlightComponent;
  let fixture: ComponentFixture<ResultHightlightComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ResultHightlightComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ResultHightlightComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
