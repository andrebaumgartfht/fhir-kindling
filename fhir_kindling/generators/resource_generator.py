import math
import pprint
from typing import List, Union, Type, Callable, Optional, Any
from fhir.resources.domainresource import DomainResource
from fhir.resources.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhir.resources.reference import Reference
from fhir.resources.fhirtypes import AbstractBaseType, AbstractType
from fhir.resources import get_fhir_model_class, FHIRAbstractModel
from fhir.resources.fhirabstractmodel import FHIRAbstractModel
from fhir.resources.fhirresourcemodel import FHIRResourceModel
import os
import pendulum
from uuid import uuid4
from abc import abstractmethod
from fhir.resources.resource import Resource
from pydantic import BaseModel

from fhir_kindling.generators.field_generator import FieldGenerator


class FieldValue(BaseModel):
    field: str
    value: Union[Any, List[Any]]


class GeneratorParameters(BaseModel):
    count: Optional[int] = None
    field_generators: Optional[List[FieldGenerator]] = None
    field_values: Optional[List[FieldValue]] = None

    # todo count and list in field values of same length


class ResourceGenerator:

    def __init__(self, resource: str, n: int = None, field_values: dict = None, disable_validation: bool = False,
                 generator_parameters: GeneratorParameters = None):
        self.resource = get_fhir_model_class(resource)
        self.params = generator_parameters
        self.field_values = field_values
        if self.field_values and not disable_validation:
            self._check_required_fields()
        self.disable_validation = disable_validation
        self.n = n
        self._value_iterators = {}
        # list to store the field names of all fields being generated
        self._generated_fields = set()

    def required_fields(self) -> List[str]:
        required_fields = []
        for field_name, field in self.resource.__fields__.items():
            if field.required:
                required_fields.append(field_name)
        return required_fields

    def fields(self):
        return self.resource.__fields__

    def generate(self):

        # if field values are given parse them into parameters
        if self.n and not self.params:
            self.params = GeneratorParameters(count=self.n)

        if self.field_values and self.n:
            self._parse_field_values()
        if not self.disable_validation:
            self._validate_params()
        resources = self._generate_resources()
        return resources

    def _generate_resources(self):
        resources = []
        for i in range(self.params.count):
            resource = self._generate_resource()
            resources.append(resource)
        return resources

    def _generate_resource(self):
        # construct a resource object to hold the generated fields
        resource = self.resource.construct()
        # disable assignment validation
        resource.Config.validate_assignment = False
        if self.params.field_values:
            for field_value in self.params.field_values:
                # update resource with field value
                self._update_with_field_value(resource, field_value)

        if self.params.field_generators:
            for generator in self.params.field_generators:
                # update resource with generated field value
                self._update_with_field_generator(resource, generator)

        # validate resource when validation is enabled
        if not self.disable_validation:
            resource = self.resource(**resource.dict(exclude_none=True))

        return resource

    def _update_with_field_value(self, resource: FHIRResourceModel, field_value: FieldValue):
        if isinstance(field_value.value, list):
            iterator = self._value_iterators.get(field_value.field)
            if not iterator:
                iterator = iter(field_value.value)
                self._value_iterators[field_value.field] = iterator
            resource.__setattr__(field_value.field, next(iterator))
        else:
            resource.__setattr__(field_value.field, field_value.value)

    def _update_with_field_generator(self, resource: FHIRResourceModel, field_generator: FieldGenerator):

        value = field_generator.generate()
        resource.__setattr__(field_generator.field, value)

    def _check_required_fields(self):
        """
        Check if all required fields are being generated by the field generators or are given as field values

        Returns:

        """
        required_fields_set = set(self.required_fields())
        if not required_fields_set.issubset(self._generated_fields):
            raise ValueError(f"Required fields {required_fields_set} not generated,"
                             f"generated fields: {self._generated_fields}")

    def _parse_field_values(self):

        params = GeneratorParameters(
            count=self.n
        )

        # todo: add support for field_values as a list of dicts

        self.params = params

    def _validate_params(self):
        # validate field values
        if self.params.field_values:
            self._validate_field_values()

        # validate field generators
        if self.params.field_generators:
            self._validate_field_generators()

        # check that the required fields are being generated
        self._check_required_fields()

    def _validate_field_values(self):
        field_values = self.params.field_values
        resource_count = self.params.count

        for field_value in field_values:
            # check for duplicates in generated fields
            if field_value.field in self._generated_fields:
                raise ValueError(f"Field value {field_value.value} is already generated")
            self._generated_fields.add(field_value.field)

            # check that the list length matches the resource count
            if isinstance(field_value.value, list):
                if len(field_value.value) != resource_count:
                    raise ValueError(f"Field value list length does not match resource count: {field_value.field}"
                                     f"Items in field value list: {len(field_value.value)},"
                                     f" resource count: {resource_count}")
            # todo check that the type of the item fits into the selected field

    def _validate_field_generators(self):
        generators = self.params.field_generators
        for resource_generator in generators:
            # check for duplicates in generated fields
            if resource_generator.field in self._generated_fields:
                raise ValueError(f"Field generator {resource_generator.field} is already generated")
            self._generated_fields.add(resource_generator.field)
            # todo validate generator values
