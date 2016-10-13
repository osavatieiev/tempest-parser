import jinja2
import six
import abc
import os
import re
from tempest_parser import const

pkg_dir = os.path.dirname(__file__)
pkg_dir = os.path.join(pkg_dir, os.pardir)
pkg_dir = os.path.normpath(pkg_dir)


@six.add_metaclass(abc.ABCMeta)
class _Base(object):
    def __init__(self):
        self.jinja2_env = self.init_jinja2_env()

    @abc.abstractmethod
    def __call__(self, payload):
        pass

    @staticmethod
    def init_jinja2_env():
        return jinja2.Environment(
            loader=jinja2.FileSystemLoader(os.path.join(pkg_dir, 'templates')),
            trim_blocks=True,
            lstrip_blocks=True)


class _TMPLBase(_Base):
    @abc.abstractproperty
    def tmpl(self):
        pass

    @staticmethod
    def _count_totals(data):
        data['totals'] = {}

        for execution in data['executions']:
            _total = _pass = _fail = _error = _na = _skip = 0
            # classes = data['tests'].keys()
            for test_class in data['tests']:
                for test in data['tests'][test_class]:
                    _total += 1
                    if execution in test['results']:
                        if test['results'][execution][
                            'result'].lower() == 'ok':
                            _pass += 1
                        elif test['results'][execution][
                            'result'].lower() == 'fail':
                            _fail += 1
                        elif test['results'][execution][
                            'result'].lower() == 'skip':
                            _skip += 1
                    else:
                        _na += 1

            data['totals'][execution] = {
                'total': _total,
                const.STATUS_PASS: _pass,
                const.STATUS_FAIL: _fail,
                const.STATUS_ERROR: _error,
                const.STATUS_NA: _na,
                const.STATUS_SKIP: _skip
            }

    def __call__(self, results, detailed=False):
        data = self.common_data()
        data.update({
            "executions": {},
            "detailed": detailed,
            "tests": results['tests']
        })

        for _execution in results['executions']:
            data['executions'][_execution] = {
                "date": results['executions'][_execution],
                "filename": os.path.basename(_execution)
            }
        self._extend_data(data)
        self._count_totals(data)

        tmpl = self.jinja2_env.get_template(self.tmpl)
        return tmpl.render(data)

    def common_data(self):
        return {
            'report': self,

            'STATUS_PASS': const.STATUS_PASS,
            'STATUS_FAIL': const.STATUS_FAIL,
            'STATUS_ERROR': const.STATUS_ERROR,
            'STATUS_NA': const.STATUS_NA,
            'STATUS_SKIP': const.STATUS_SKIP,

            'status_description': {
                const.STATUS_PASS: 'Pass',
                const.STATUS_FAIL: 'Fail',
                const.STATUS_ERROR: 'Error',
                const.STATUS_NA: 'NA',
                const.STATUS_SKIP: 'Skip'}}

    def _extend_data(self, data):
        pass


# Trending report
class HTMLTrendingReport(_TMPLBase):
    tmpl = "tempest_trending_report.html"


class HTMLErrorsReport(_TMPLBase):
    tmpl = "tempest_errors_report.html"

    def _extend_data(self, data):
        # list with unique messages
        skipped_messages = {}
        failed_messages = {}

        # Reverse source list and get unique errors
        for execution in data['executions']:

            for test_class in data['tests']:
                for test in data['tests'][test_class]:

                    main_message = test['results'][execution]['message']

                    _trace = test['results'][execution]['trace']
                    _trace_details = ""
                    _trace_additional = []
                    for line in _trace.split('\n'):
                        if line.startswith("Details:"):
                            _trace_details = line[9:]
                        elif not line.startswith("Trace") \
                                and not re.match(r'\s', line):
                            _trace_additional.append(line)
                    _trace_messages = ", ".join(_trace_additional)

                    if _trace_details.__len__() == 0 \
                            and main_message.__len__() == 0:
                        main_message = "Fail message can't be extracted"
                    elif main_message.__len__() == 0:
                        main_message = _trace_details

                    _dict = {
                        'test_class': test_class,
                        'test_name': test['test_name'],
                        'set_name': test['set_name'],
                        'test_options': test['test_options'],
                        'trace_details': _trace_details,
                        'trace_additional': _trace_messages
                    }
                    _dict.update(test['results'][execution])

                    if _dict['result'].lower() == 'skip':
                        if main_message not in skipped_messages:
                            skipped_messages[main_message] = []
                        skipped_messages[main_message].append(_dict)

                    if _dict['result'].lower() == 'fail':
                        if main_message not in failed_messages:
                            failed_messages[main_message] = []
                        failed_messages[main_message].append(_dict)

        data['unique_skips'] = skipped_messages
        data['uniqie_fails'] = failed_messages


class ReportToFile(object):
    def __init__(self, report, target):
        self.report = report
        self.target = target

    def __call__(self, payload, detailed=False):
        payload = self.report(payload, detailed)

        if isinstance(self.target, six.string_types):
            self._wrapped_dump(payload)
        else:
            self._dump(payload, self.target)

    def _wrapped_dump(self, payload):
        with open(self.target, 'wt') as target:
            self._dump(payload, target)

    @staticmethod
    def _dump(payload, target):
        target.write(payload)
